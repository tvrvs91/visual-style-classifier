package com.diploma.psc;

import org.junit.jupiter.api.AfterEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.RabbitMQContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

import com.diploma.psc.photo.PhotoRepository;
import com.diploma.psc.style.PhotoStyleRepository;
import com.diploma.psc.user.UserRepository;

/**
 * Базовый класс для интеграционных тестов: единственный экземпляр Postgres,
 * RabbitMQ и MinIO поднимается контейнерами на весь testRun (singleton-pattern),
 * между тестами очищаются только данные.
 *
 * MinIO биндится через GenericContainer (модуль org.testcontainers:minio
 * экспортирует только credentials helper, но всё, что нам нужно — endpoint).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
public abstract class IntegrationTestBase {

    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine")
                    .withDatabaseName("psc_test")
                    .withUsername("psc_test")
                    .withPassword("psc_test");

    static final RabbitMQContainer RABBIT =
            new RabbitMQContainer("rabbitmq:3.13-management-alpine");

    static final GenericContainer<?> MINIO =
            new GenericContainer<>("minio/minio:latest")
                    .withCommand("server /data")
                    .withEnv("MINIO_ROOT_USER", "test_admin")
                    .withEnv("MINIO_ROOT_PASSWORD", "test_admin_password")
                    .withExposedPorts(9000);

    static {
        POSTGRES.start();
        RABBIT.start();
        MINIO.start();
    }

    @DynamicPropertySource
    static void registerProperties(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        r.add("spring.datasource.username", POSTGRES::getUsername);
        r.add("spring.datasource.password", POSTGRES::getPassword);

        r.add("spring.rabbitmq.host", RABBIT::getHost);
        r.add("spring.rabbitmq.port", RABBIT::getAmqpPort);
        r.add("spring.rabbitmq.username", RABBIT::getAdminUsername);
        r.add("spring.rabbitmq.password", RABBIT::getAdminPassword);

        String minioEndpoint = "http://" + MINIO.getHost() + ":" + MINIO.getMappedPort(9000);
        r.add("app.minio.endpoint", () -> minioEndpoint);
        r.add("app.minio.public-endpoint", () -> minioEndpoint);
        r.add("app.minio.access-key", () -> "test_admin");
        r.add("app.minio.secret-key", () -> "test_admin_password");
        r.add("app.minio.bucket", () -> "test-photos");

        r.add("app.jwt.secret", () -> "integration-test-secret-must-be-at-least-32-bytes-long");
    }

    @Autowired protected PhotoRepository photoRepository;
    @Autowired protected PhotoStyleRepository photoStyleRepository;
    @Autowired protected UserRepository userRepository;

    @AfterEach
    void resetData() {
        photoStyleRepository.deleteAll();
        photoRepository.deleteAll();
        userRepository.deleteAll();
    }
}
