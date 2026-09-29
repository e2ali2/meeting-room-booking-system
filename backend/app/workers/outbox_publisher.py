import json
from datetime import datetime, timezone

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import OutboxEvent


RABBITMQ_HOST = "localhost"
EXCHANGE_NAME = "booking.events"

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
    publish_pending_events()
