package com.diploma.psc.photo;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Поиск визуально похожих фотографий через cosine similarity в пространстве
 * 1280-мерных эмбеддингов EfficientNet-B0 (выход global average pooling, до
 * классифицирующей головы).
 *
 * Преимущество над поиском по совпадению style-тегов: использует ПОЛНОЕ
 * представление изображения в выученном пространстве признаков, а не его
 * дискретную проекцию на 7 классов. Два кадра могут получить разные top-1
 * теги (из-за мелких различий в softmax), но при этом быть очень близкими
 * в embedding-пространстве — и наоборот.
 *
 * Реализация: брут-форс O(N·1280) в Java. Для коллекции в 10k фото это
 * ~40MB памяти и ~10ms на запрос — приемлемо. Для большего масштаба
 * следует использовать pgvector / Qdrant / Faiss.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SimilarityService {

    private static final TypeReference<List<Double>> EMBEDDING_TYPE = new TypeReference<>() {};

    private final PhotoFeaturesRepository photoFeaturesRepository;
    private final PhotoRepository photoRepository;
    private final ObjectMapper objectMapper;

    /**
     * Найти top-N фотографий пользователя, наиболее похожих на заданную
     * по embedding cosine similarity. Целевая фотография исключается из
     * выдачи.
     */
    @Transactional(readOnly = true)
    public List<Long> findSimilarPhotoIds(Long userId, Long targetPhotoId, int limit) {
        // Целевой embedding
        var targetOpt = photoFeaturesRepository.findByPhotoId(targetPhotoId);
        if (targetOpt.isEmpty()) {
            return List.of();
        }
        double[] target = parseEmbedding(targetOpt.get().getEmbedding());
        if (target.length == 0) {
            return List.of();
        }
        double targetNorm = norm(target);
        if (targetNorm == 0.0) {
            return List.of();
        }

        // Все остальные embedding'и пользователя (только DONE-фото)
        var rows = photoFeaturesRepository.findEmbeddingsByUserId(userId);

        record Scored(Long photoId, double similarity) {}
        List<Scored> scored = new ArrayList<>(rows.size());
        for (var row : rows) {
            if (row.getPhotoId().equals(targetPhotoId)) continue;
            double[] vec = parseEmbedding(row.getEmbedding());
            if (vec.length != target.length) continue;
            double sim = cosineSimilarity(target, vec, targetNorm, norm(vec));
            scored.add(new Scored(row.getPhotoId(), sim));
        }

        scored.sort(Comparator.comparingDouble(Scored::similarity).reversed());

        return scored.stream()
                .limit(limit)
                .map(Scored::photoId)
                .toList();
    }

    // ---- math --------------------------------------------------------------

    private double[] parseEmbedding(String json) {
        if (json == null || json.isBlank() || json.equals("[]")) return new double[0];
        try {
            List<Double> list = objectMapper.readValue(json, EMBEDDING_TYPE);
            double[] arr = new double[list.size()];
            for (int i = 0; i < arr.length; i++) arr[i] = list.get(i);
            return arr;
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse embedding: {}", e.getMessage());
            return new double[0];
        }
    }

    private static double norm(double[] v) {
        double s = 0;
        for (double x : v) s += x * x;
        return Math.sqrt(s);
    }

    private static double cosineSimilarity(double[] a, double[] b, double normA, double normB) {
        if (normA == 0 || normB == 0) return 0;
        double dot = 0;
        for (int i = 0; i < a.length; i++) dot += a[i] * b[i];
        return dot / (normA * normB);
    }
}
