package com.diploma.psc.photo;

import com.diploma.psc.auth.UserDetailsServiceImpl.AuthUser;
import com.diploma.psc.classification.ClassificationProducer;
import com.diploma.psc.classification.ClassificationTask;
import com.diploma.psc.photo.dto.PhotoResponse;
import com.diploma.psc.photo.dto.StyleTagResponse;
import com.diploma.psc.style.PhotoStyle;
import com.diploma.psc.user.User;
import com.diploma.psc.user.UserRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
@Slf4j
public class PhotoService {

    private static final Set<String> ALLOWED_CONTENT_TYPES =
            Set.of("image/jpeg", "image/jpg", "image/png", "image/webp");

    private static final TypeReference<List<String>> PALETTE_TYPE = new TypeReference<>() {};
    private static final TypeReference<Map<String, Double>> SCORES_TYPE = new TypeReference<>() {};

    private final PhotoRepository photoRepository;
    private final UserRepository userRepository;
    private final MinioService minioService;
    private final ClassificationProducer producer;
    private final PhotoFeaturesRepository photoFeaturesRepository;
    private final SimilarityService similarityService;
    private final ObjectMapper objectMapper;

    @Transactional
    public PhotoResponse upload(MultipartFile file, AuthUser principal) {
        validate(file);

        User user = userRepository.findById(principal.getUserId())
                .orElseThrow(() -> new IllegalStateException("User not found"));

        String key = minioService.upload(file, user.getId());

        Photo photo = Photo.builder()
                .user(user)
                .s3Key(key)
                .status(PhotoStatus.PENDING)
                .build();
        photo = photoRepository.save(photo);

        producer.send(new ClassificationTask(photo.getId(), key, minioService.getBucket()));
        return toResponse(photo);
    }

    @Transactional
    public void delete(Long id, AuthUser principal) {
        Photo photo = photoRepository.findByIdAndUserId(id, principal.getUserId())
                .orElseThrow(() -> new IllegalArgumentException("Photo not found"));
        String key = photo.getS3Key();
        photoRepository.delete(photo);
        // MinIO удаляется после успешного коммита транзакции; если упадёт — сирота в S3,
        // но запись в БД уже не вернёт её клиенту (можно подчистить сборщиком мусора).
        minioService.delete(key);
    }

    @Transactional(readOnly = true)
    public PhotoResponse get(Long id, AuthUser principal) {
        Photo photo = photoRepository.findByIdAndUserId(id, principal.getUserId())
                .orElseThrow(() -> new IllegalArgumentException("Photo not found"));
        return toResponse(photo);
    }

    @Transactional(readOnly = true)
    public Page<PhotoResponse> list(AuthUser principal, int page, int size) {
        var pageable = PageRequest.of(page, size, Sort.by("uploadedAt").descending());
        return photoRepository.findByUserId(principal.getUserId(), pageable).map(this::toResponse);
    }

    @Transactional(readOnly = true)
    public Page<PhotoResponse> searchByStyle(AuthUser principal, String style, double minConfidence,
                                             int page, int size) {
        var pageable = PageRequest.of(page, size, Sort.by("uploadedAt").descending());
        return photoRepository.searchByStyle(principal.getUserId(), style, minConfidence, pageable)
                .map(this::toResponse);
    }

    @Transactional(readOnly = true)
    public Page<PhotoResponse> searchByColor(AuthUser principal, String color, int page, int size) {
        var pageable = PageRequest.of(page, size);
        return photoRepository.searchByColor(principal.getUserId(), color, pageable)
                .map(this::toResponse);
    }

    private void validate(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new IllegalArgumentException("File is empty");
        String ct = file.getContentType();
        if (ct == null || !ALLOWED_CONTENT_TYPES.contains(ct.toLowerCase())) {
            throw new IllegalArgumentException("Unsupported content type: " + ct);
        }
    }

    @Transactional(readOnly = true)
    public List<PhotoResponse> similar(Long photoId, AuthUser principal, int limit) {
        // проверка владения
        photoRepository.findByIdAndUserId(photoId, principal.getUserId())
                .orElseThrow(() -> new IllegalArgumentException("Photo not found"));

        List<Long> similarIds = similarityService.findSimilarPhotoIds(
                principal.getUserId(), photoId, limit);

        if (similarIds.isEmpty()) return List.of();

        // Сохраняем порядок по убыванию similarity
        var found = photoRepository.findAllById(similarIds);
        var byId = new java.util.HashMap<Long, Photo>();
        for (Photo p : found) byId.put(p.getId(), p);

        return similarIds.stream()
                .map(byId::get)
                .filter(java.util.Objects::nonNull)
                .map(this::toResponse)
                .toList();
    }

    private PhotoResponse toResponse(Photo photo) {
        List<StyleTagResponse> tags = photo.getStyles().stream()
                .sorted(Comparator.comparingDouble(PhotoStyle::getConfidence).reversed())
                .map(ps -> new StyleTagResponse(ps.getStyle().getName(), ps.getConfidence()))
                .toList();

        // Подмешиваем palette и scores из PhotoFeatures (могут отсутствовать у
        // фото залитых ДО введения этой фичи или ещё в обработке)
        List<String> palette = List.of();
        Map<String, Double> scores = Map.of();
        var features = photoFeaturesRepository.findByPhotoId(photo.getId()).orElse(null);
        if (features != null) {
            try {
                if (features.getPalette() != null && !features.getPalette().isBlank()) {
                    palette = objectMapper.readValue(features.getPalette(), PALETTE_TYPE);
                }
                if (features.getScores() != null && !features.getScores().isBlank()) {
                    scores = objectMapper.readValue(features.getScores(), SCORES_TYPE);
                }
            } catch (JsonProcessingException e) {
                log.warn("Failed to deserialize features for photo {}: {}", photo.getId(), e.getMessage());
            }
        }

        return new PhotoResponse(
                photo.getId(),
                photo.getS3Key(),
                minioService.presignedGetUrl(photo.getS3Key()),
                photo.getUploadedAt(),
                photo.getStatus(),
                tags,
                palette,
                scores
        );
    }
}
