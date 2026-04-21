package com.diploma.psc.classification;

import com.diploma.psc.photo.Photo;
import com.diploma.psc.photo.PhotoRepository;
import com.diploma.psc.photo.PhotoStatus;
import com.diploma.psc.style.PhotoStyle;
import com.diploma.psc.style.PhotoStyleId;
import com.diploma.psc.style.PhotoStyleRepository;
import com.diploma.psc.style.Style;
import com.diploma.psc.style.StyleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
@Slf4j
public class ClassificationConsumer {

    private final PhotoRepository photoRepository;
    private final StyleRepository styleRepository;
    private final PhotoStyleRepository photoStyleRepository;

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

        photo.setStatus(PhotoStatus.DONE);
        photoRepository.save(photo);
    }
}
