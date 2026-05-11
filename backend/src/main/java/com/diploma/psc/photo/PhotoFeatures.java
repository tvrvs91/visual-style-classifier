package com.diploma.psc.photo;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

/**
 * Расширенные ML-фичи фотографии — хранятся 1:1 с {@link Photo}, в отдельной
 * таблице чтобы не тянуть тяжёлые JSON-поля (embedding ~25KB) при стандартных
 * listing-запросах галереи.
 *
 * Заполняется в {@code ClassificationConsumer} при получении результата от
 * ML-сервиса. Используется {@code SimilarityService} для embedding-based
 * поиска похожих кадров через cosine similarity.
 */
@Entity
@Table(name = "photo_features")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PhotoFeatures {

    @Id
    @Column(name = "photo_id")
    private Long photoId;

    @OneToOne(fetch = FetchType.LAZY)
    @MapsId
    @JoinColumn(name = "photo_id")
    private Photo photo;

    /** JSON-массив 1280 float'ов — выход предпоследнего слоя EfficientNet-B0. */
    @Column(columnDefinition = "TEXT", nullable = false)
    private String embedding;

    /** JSON-массив из 5 hex-строк — доминирующие цвета через k-means. */
    @Column(columnDefinition = "TEXT", nullable = false)
    private String palette;

    /** JSON-объект {brightness, contrast, saturation, warmth, sharpness} в [0,1]. */
    @Column(columnDefinition = "TEXT", nullable = false)
    private String scores;

    @Column(name = "extracted_at", nullable = false, updatable = false)
    private Instant extractedAt;

    @PrePersist
    void onCreate() {
        if (extractedAt == null) extractedAt = Instant.now();
    }
}
