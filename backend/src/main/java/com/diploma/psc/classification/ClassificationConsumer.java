package com.diploma.psc.classification;

import com.diploma.psc.photo.Photo;
import com.diploma.psc.photo.PhotoFeatures;
import com.diploma.psc.photo.PhotoFeaturesRepository;
import com.diploma.psc.photo.PhotoRepository;
import com.diploma.psc.photo.PhotoStatus;
import com.diploma.psc.style.PhotoStyle;
import com.diploma.psc.style.PhotoStyleId;
import com.diploma.psc.style.PhotoStyleRepository;
import com.diploma.psc.style.Style;
import com.diploma.psc.style.StyleRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class ClassificationConsumer {

    private final PhotoRepository photoRepository;
    private final StyleRepository styleRepository;
    private final PhotoStyleRepository photoStyleRepository;
    private final PhotoFeaturesRepository photoFeaturesRepository;
    private final ObjectMapper objectMapper;

    @RabbitListener(queues = "${app.rabbitmq.result-queue}")
    @Transactional
    public void onResult(ClassificationResult result) {
        log.info("Received classification result for photoId={} status={}", result.photoId(), result.status());

        Photo photo = photoRepository.findById(result.photoId()).orElse(null);
        if (photo == null) {
            log.warn("Photo {} not found — dropping result", result.photoId());
            return;
        }

        if (!"OK".equalsIgnoreCase(result.status())) {
            photo.setStatus(PhotoStatus.FAILED);
            photoRepository.save(photo);
            log.warn("Classification failed for photo {}: {}", result.photoId(), result.error());
            return;
        }

        // 1. Style tags ------------------------------------------------------
        photoStyleRepository.deleteByPhotoId(photo.getId());
        photoStyleRepository.flush();

        if (result.styles() != null) {
            for (ClassificationResult.StyleScore score : result.styles()) {
                Style style = styleRepository.findByName(score.name()).orElse(null);
                if (style == null) {
                    log.warn("Unknown style '{}' — skipping", score.name());
                    continue;
                }
                PhotoStyle ps = PhotoStyle.builder()
                        .id(new PhotoStyleId(photo.getId(), style.getId()))
                        .photo(photo)
                        .style(style)
                        .confidence(score.confidence())
                        .build();
                photoStyleRepository.save(ps);
            }
        }

        // 2. Extended ML features (embedding + palette + scores) ------------
        saveFeatures(photo, result);

        photo.setStatus(PhotoStatus.DONE);
        photoRepository.save(photo);
    }

    private void saveFeatures(Photo photo, ClassificationResult result) {
        try {
            String embeddingJson = result.embedding() != null
                    ? objectMapper.writeValueAsString(result.embedding())
                    : "[]";
            String paletteJson = result.palette() != null
                    ? objectMapper.writeValueAsString(result.palette())
                    : "[]";
            Map<String, Double> scores = result.scores() != null ? result.scores() : Map.of();
            String scoresJson = objectMapper.writeValueAsString(scores);

            // @MapsId: photoId выводится Hibernate'ом из photo.id — НЕ устанавливаем явно
            PhotoFeatures features = photoFeaturesRepository.findByPhotoId(photo.getId())
                    .orElseGet(() -> PhotoFeatures.builder().photo(photo).build());
            features.setEmbedding(embeddingJson);
            features.setPalette(paletteJson);
            features.setScores(scoresJson);
            photoFeaturesRepository.save(features);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize features for photo {}: {}", photo.getId(), e.getMessage());
        }
    }
}
