package com.diploma.psc.classification;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class ClassificationProducer {

    private final RabbitTemplate rabbitTemplate;

    @Value("${app.rabbitmq.exchange}")
    private String exchange;

    @Value("${app.rabbitmq.task-routing-key}")
    private String routingKey;

    public void send(ClassificationTask task) {
        log.info("Publishing classification task for photoId={} key={}", task.photoId(), task.s3Key());
        rabbitTemplate.convertAndSend(exchange, routingKey, task);
    }
}
