package com.diploma.psc.classification;

public record ClassificationTask(
        Long photoId,
        String s3Key,
        String bucket
) {}
