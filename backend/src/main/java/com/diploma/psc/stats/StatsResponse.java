package com.diploma.psc.stats;

import com.diploma.psc.photo.PhotoStatus;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record StatsResponse(
        String email,
        Instant memberSince,
        long totalPhotos,
        Map<PhotoStatus, Long> byStatus,
        List<StyleCount> topStyles
) {
    public record StyleCount(String name, long count, double avgConfidence) {}
}
