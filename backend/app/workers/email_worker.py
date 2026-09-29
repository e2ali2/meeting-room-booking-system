import json

import pika


RABBITMQ_HOST = "localhost"
QUEUE_NAME = "email.notifications"


def process_message(ch, method, properties, body):
    try:
        event = json.loads(body)

        print("\nПолучено событие:")
        print(json.dumps(event, indent=2))

        if event.get("simulate_failure") is True:
            raise RuntimeError("Simulated email sending failure")

        print(
            f"\n[EMAIL] Обрабатываем {event.get('event_type')} "
            f"для бронирования {event.get('booking_id')}"
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("[ACK] Сообщение успешно обработано")

    except Exception as exc:
        print(f"\n[ERROR] Ошибка обработки сообщения: {exc}")

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )

        print("[NACK] Сообщение отклонено и направлено в DLQ")


def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_message,
        auto_ack=False,
    )

    print(f"Email Worker запущен. Ожидаю сообщения из '{QUEUE_NAME}'...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nEmail Worker остановлен.")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
