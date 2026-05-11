package com.diploma.psc.photo.dto;

import com.diploma.psc.photo.PhotoStatus;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record PhotoResponse(
        Long id,
        String s3Key,
        String url,
        Instant uploadedAt,
        PhotoStatus status,
        List<StyleTagResponse> styles,
        List<String> palette,           // ["#aabbcc", ...] — 5 hex-цветов или пусто
        Map<String, Double> scores      // {brightness, contrast, saturation, warmth, sharpness} или пусто
) {}
