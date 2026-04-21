package com.diploma.psc.config;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

@Configuration
public class MinioConfig {

    /**
     * Client used for server-side operations (upload, download, bucket mgmt).
     * Points at the internal Docker endpoint (e.g. http://minio:9000).
     */
    @Bean
    @Primary
    public MinioClient minioClient(
            @Value("${app.minio.endpoint}") String endpoint,
            @Value("${app.minio.access-key}") String accessKey,
            @Value("${app.minio.secret-key}") String secretKey
    ) {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }

    /**
     * Client used only to generate presigned URLs. Points at the browser-visible
     * endpoint (e.g. http://localhost:9000) so generated URLs are resolvable
     * outside the Docker network. The signature is bound to this host, so do not
     * use this client for actual S3 calls from inside the backend.
     */
    @Bean("minioPresignClient")
    public MinioClient minioPresignClient(
            @Value("${app.minio.public-endpoint}") String publicEndpoint,
            @Value("${app.minio.access-key}") String accessKey,
            @Value("${app.minio.secret-key}") String secretKey
    ) {
        return MinioClient.builder()
                .endpoint(publicEndpoint)
                .credentials(accessKey, secretKey)
                .region("us-east-1")
                .build();
    }
}
