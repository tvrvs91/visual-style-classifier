package com.diploma.psc.classification;

import com.diploma.psc.IntegrationTestBase;
import com.diploma.psc.photo.Photo;
import com.diploma.psc.photo.PhotoStatus;
import com.diploma.psc.style.PhotoStyle;
import com.diploma.psc.style.StyleRepository;
import com.diploma.psc.user.User;
import org.awaitility.Awaitility;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;

import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ClassificationConsumerTest extends IntegrationTestBase {

    @Autowired RabbitTemplate rabbitTemplate;
    @Autowired StyleRepository styleRepository;

    @Value("${app.rabbitmq.exchange}")
    String exchange;

    @Value("${app.rabbitmq.result-routing-key}")
    String resultRoutingKey;

    @Test
    void successful_result_persists_styles_and_marks_done() {
        User user = userRepository.save(User.builder()
                .email("dave@example.com").password("hashed").build());
        Photo photo = photoRepository.save(Photo.builder()
                .user(user).s3Key("user-1/x.jpg").status(PhotoStatus.PENDING).build());

        ClassificationResult result = new ClassificationResult(
                photo.getId(),
                "OK",
                null,
                List.of(
                        new ClassificationResult.StyleScore("moody", 0.72),
                        new ClassificationResult.StyleScore("dark", 0.21)
                )
        );

        rabbitTemplate.convertAndSend(exchange, resultRoutingKey, result);

        Long moodyId = styleRepository.findByName("moody").orElseThrow().getId();
        Long darkId = styleRepository.findByName("dark").orElseThrow().getId();

        Awaitility.await().atMost(Duration.ofSeconds(10)).untilAsserted(() -> {
            Photo refreshed = photoRepository.findById(photo.getId()).orElseThrow();
            assertThat(refreshed.getStatus()).isEqualTo(PhotoStatus.DONE);

            List<PhotoStyle> styles = photoStyleRepository.findByPhotoId(photo.getId());
            assertThat(styles).hasSize(2);
            // FK через embedded id — без обращения к lazy-proxy Style
            assertThat(styles).extracting(ps -> ps.getId().getStyleId())
                    .containsExactlyInAnyOrder(moodyId, darkId);
        });
    }

    @Test
    void error_result_marks_photo_failed() {
        User user = userRepository.save(User.builder()
                .email("eve@example.com").password("hashed").build());
        Photo photo = photoRepository.save(Photo.builder()
                .user(user).s3Key("user-2/y.jpg").status(PhotoStatus.PENDING).build());

        ClassificationResult result = new ClassificationResult(
                photo.getId(), "ERROR", "model crashed", List.of());
        rabbitTemplate.convertAndSend(exchange, resultRoutingKey, result);

        Awaitility.await().atMost(Duration.ofSeconds(10)).untilAsserted(() -> {
            Photo refreshed = photoRepository.findById(photo.getId()).orElseThrow();
            assertThat(refreshed.getStatus()).isEqualTo(PhotoStatus.FAILED);
            assertThat(photoStyleRepository.findByPhotoId(photo.getId())).isEmpty();
        });
    }
}
