import json
import os
import time
from datetime import datetime, timezone

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import OutboxEvent


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
POLL_INTERVAL_SECONDS = int(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
EXCHANGE_NAME = "booking.events"
EMAIL_QUEUE = "email.notifications.v2"
DEAD_LETTER_EXCHANGE = "booking.events.dlx"
DEAD_LETTER_QUEUE = "email.notifications.v2.dlq"

ROUTING_KEYS = {
    "BookingCreated": "booking.created",
    "BookingUpdated": "booking.updated",
    "BookingCancelled": "booking.cancelled",
}


def publish_pending_events():
    db = Session(engine)

    connection = None

    try:
        events = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.created_at)
        ).all()

        if not events:
            print("Нет PENDING событий.")
            return

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )
        channel.exchange_declare(
            exchange=DEAD_LETTER_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        channel.queue_declare(
            queue=EMAIL_QUEUE,
            durable=True,
            arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE},
        )
        channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DEAD_LETTER_EXCHANGE,
            queue=DEAD_LETTER_QUEUE,
            routing_key="#",
        )
        for routing_key in ROUTING_KEYS.values():
            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=EMAIL_QUEUE,
                routing_key=routing_key,
            )

        for event in events:
            routing_key = ROUTING_KEYS.get(event.event_type)

            if routing_key is None:
                print(f"Неизвестный event_type: {event.event_type}")
                event.status = "FAILED"
                event.retry_count += 1
                db.commit()
                continue

            try:
                channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=routing_key,
                    body=json.dumps(event.payload),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,
                        message_id=str(event.event_id),
                    ),
                )

                event.status = "PUBLISHED"
                event.published_at = datetime.now(timezone.utc)
                db.commit()

                print(
                    f"[PUBLISHED] {event.event_type} "
                    f"{event.event_id} -> {routing_key}"
                )

            except Exception as exc:
                db.rollback()

                failed_event = db.get(OutboxEvent, event.event_id)

                if failed_event is not None:
                    failed_event.retry_count += 1
                    db.commit()

                print(
                    f"[ERROR] Не удалось опубликовать "
                    f"{event.event_id}: {exc}"
                )

    finally:
        if connection is not None and connection.is_open:
            connection.close()

        db.close()


if __name__ == "__main__":
    print("[OUTBOX] Publisher started")
    while True:
        try:
            publish_pending_events()
        except Exception as exc:
            print(f"[OUTBOX ERROR] {exc}")
        time.sleep(POLL_INTERVAL_SECONDS)
