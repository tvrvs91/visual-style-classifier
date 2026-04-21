package com.diploma.psc.classification;

import java.util.List;

public record ClassificationResult(
        Long photoId,
        String status,
        String error,
        List<StyleScore> styles
) {
    public record StyleScore(String name, double confidence) {}
}
