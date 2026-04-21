import json
import logging
import threading
import time
from typing import Callable

import pika
from pika.exceptions import AMQPConnectionError

from .config import settings

log = logging.getLogger(__name__)


class RabbitMQWorker:
    """Blocking pika consumer running in a background thread.

    Declares the direct exchange + task/result queues so it works regardless
    of whether the Spring side boots first.
    """

    def __init__(self, handler: Callable[[dict], dict]):
        self.handler = handler
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="rabbit-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._consume()
            except AMQPConnectionError as e:
                log.warning("RabbitMQ connection lost (%s); reconnecting in 5s.", e)
                time.sleep(5)
            except Exception:
                log.exception("Consumer crashed; restarting in 5s.")
                time.sleep(5)

    def _consume(self) -> None:
        params = pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password),
            heartbeat=30,
            blocked_connection_timeout=60,
        )
        conn = pika.BlockingConnection(params)
        channel = conn.channel()

        channel.exchange_declare(exchange=settings.exchange, exchange_type="direct", durable=True)
        channel.queue_declare(queue=settings.task_queue, durable=True)
        channel.queue_declare(queue=settings.result_queue, durable=True)
        channel.queue_bind(queue=settings.task_queue, exchange=settings.exchange,
                           routing_key=settings.task_routing_key)
        channel.queue_bind(queue=settings.result_queue, exchange=settings.exchange,
                           routing_key=settings.result_routing_key)
        channel.basic_qos(prefetch_count=2)

        def on_message(ch, method, properties, body):
            try:
                task = json.loads(body.decode("utf-8"))
                log.info("Received task: %s", task)
                result = self.handler(task)
                ch.basic_publish(
                    exchange=settings.exchange,
                    routing_key=settings.result_routing_key,
                    body=json.dumps(result).encode("utf-8"),
                    properties=pika.BasicProperties(content_type="application/json",
                                                    delivery_mode=2),
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                log.exception("Error handling message; rejecting without requeue.")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue=settings.task_queue, on_message_callback=on_message)
        log.info("Consumer started on queue '%s'", settings.task_queue)

        while not self._stop.is_set():
            conn.process_data_events(time_limit=1)

        channel.close()
        conn.close()
