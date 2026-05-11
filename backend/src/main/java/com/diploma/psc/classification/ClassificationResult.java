package com.diploma.psc.classification;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;
import java.util.Map;

/**
 * Сообщение из очереди классификационных результатов от Python ML-сервиса.
 *
 * Поля embedding/palette/scores опциональны (могут отсутствовать в старых
 * сообщениях или при работе ML в heuristic-режиме) — {@code @JsonIgnoreProperties}
 * на классе и null-tolerant парсинг.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ClassificationResult(
        Long photoId,
        String status,
        String error,
        List<StyleScore> styles,
        List<Double> embedding,        // 1280-dim или null
        List<String> palette,          // ["#aabbcc", ...] или []
        Map<String, Double> scores     // {brightness, contrast, ...} или {}
) {
    public record StyleScore(String name, double confidence) {}
}
