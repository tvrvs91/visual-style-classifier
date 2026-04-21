package com.diploma.psc.photo.dto;

import com.diploma.psc.photo.PhotoStatus;

import java.time.Instant;
import java.util.List;

public record PhotoResponse(
        Long id,
        String s3Key,
        String url,
        Instant uploadedAt,
        PhotoStatus status,
        List<StyleTagResponse> styles
) {}
