import json
import os
import smtplib
from email.message import EmailMessage

import pika
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.database import engine
from app.models import User


load_dotenv()

RABBITMQ_HOST = "localhost"
QUEUE_NAME = "email.notifications"

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")


def get_user_email(user_id):
    with Session(engine) as db:
        user = db.get(User, user_id)

        if not user:
            raise RuntimeError(f"User {user_id} not found")

        return user.email


def build_email(event, recipient):
    event_type = event.get("event_type")
    room_id = event.get("room_id")
    start_time = event.get("start_time")
    end_time = event.get("end_time")

    subjects = {
        "BookingCreated": "Переговорная забронирована",
        "BookingUpdated": "Бронирование изменено",
        "BookingCancelled": "Бронирование отменено",
    }

    message = EmailMessage()
    message["Subject"] = subjects.get(
        event_type,
        "Уведомление Meeting Room Booking System",
    )
    message["From"] = SMTP_FROM
    message["To"] = recipient

    message.set_content(
        f"""Meeting Room Booking System

Событие: {event_type}
Переговорная: {room_id}
Начало: {start_time}
Окончание: {end_time}

Это автоматическое уведомление.
"""
    )

    return message


def send_email(message):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM]):
        raise RuntimeError("SMTP settings are not configured")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)


def process_message(ch, method, properties, body):
    try:
        event = json.loads(body)

        print("\nПолучено сообщение:")
        print(json.dumps(event, indent=2, ensure_ascii=False))

        if event.get("simulate_failure") is True:
            raise RuntimeError("Simulated email sending failure")

        user_id = event.get("user_id")

        if not user_id:
            raise RuntimeError("user_id is missing in event")

        recipient = get_user_email(user_id)

        message = build_email(event, recipient)
        send_email(message)

        print(f"\n[EMAIL] Письмо отправлено: {recipient}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("[ACK] Сообщение подтверждено")

    except Exception as error:
        print(f"\n[ERROR] {error}")

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )


def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    channel = connection.channel()

    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_message,
        auto_ack=False,
    )

    print("[WORKER] Waiting for email notifications...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
