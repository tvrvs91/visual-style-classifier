package com.diploma.psc.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Value("${app.rabbitmq.exchange}")
    private String exchangeName;

    @Value("${app.rabbitmq.classification-queue}")
    private String taskQueue;

    @Value("${app.rabbitmq.result-queue}")
    private String resultQueue;

    @Value("${app.rabbitmq.task-routing-key}")
    private String taskRoutingKey;

    @Value("${app.rabbitmq.result-routing-key}")
    private String resultRoutingKey;

    @Bean
    public DirectExchange classificationExchange() {
        return new DirectExchange(exchangeName, true, false);
    }

    @Bean
    public Queue taskQueue() {
        return QueueBuilder.durable(taskQueue).build();
    }

    @Bean
    public Queue resultQueue() {
        return QueueBuilder.durable(resultQueue).build();
    }

    @Bean
    public Binding taskBinding(Queue taskQueue, DirectExchange classificationExchange) {
        return BindingBuilder.bind(taskQueue).to(classificationExchange).with(taskRoutingKey);
    }

    @Bean
    public Binding resultBinding(Queue resultQueue, DirectExchange classificationExchange) {
        return BindingBuilder.bind(resultQueue).to(classificationExchange).with(resultRoutingKey);
    }

    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory, MessageConverter converter) {
        RabbitTemplate template = new RabbitTemplate(connectionFactory);
        template.setMessageConverter(converter);
        template.setExchange(exchangeName);
        return template;
    }
}
