import json
import os
import smtplib
from urllib import error as urlerror
from urllib import request as urlrequest
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from html import escape
from zoneinfo import ZoneInfo

import pika
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Office, Room, User


load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = "email.notifications.v2"
EXCHANGE_NAME = "booking.events"
DEAD_LETTER_EXCHANGE = "booking.events.dlx"
DEAD_LETTER_QUEUE = "email.notifications.v2.dlq"
ROUTING_KEYS = ("booking.created", "booking.updated", "booking.cancelled")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "ssl").lower()
UNISENDER_API_KEY = os.getenv("UNISENDER_API_KEY")
UNISENDER_API_URL = os.getenv(
    "UNISENDER_API_URL",
    "https://goapi.unisender.ru/ru/transactional/api/v1/email/send.json",
)
EMAIL_FROM = os.getenv("EMAIL_FROM") or SMTP_FROM
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Meeting Room Booking")
NOTIFICATION_DELIVERY = os.getenv("NOTIFICATION_DELIVERY", "rabbitmq").lower()
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def get_booking_context(user_id, room_id):
    with Session(engine) as db:
        user = db.get(User, user_id) if user_id else None
        room_row = db.execute(
            select(Room, Office)
            .join(Office, Office.office_id == Room.office_id)
            .where(Room.room_id == room_id)
        ).first() if room_id else None

        return {
            "user_name": user.name if user else "Коллега",
            "user_email": user.email if user else None,
            "room_name": room_row[0].name if room_row else "Переговорная",
            "room_floor": room_row[0].floor if room_row else None,
            "office_name": room_row[1].name if room_row else "Офис",
            "office_address": room_row[1].address if room_row else None,
        }


def format_moscow_time(value):
    if not value:
        return "Не указано"

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y, %H:%M")


def build_email(event, recipient, context=None):
    context = context or {}
    event_type = event.get("event_type")
    start_time = format_moscow_time(event.get("start_time"))
    end_time = format_moscow_time(event.get("end_time"))
    room_name = context.get("room_name") or "Переговорная"
    office_name = context.get("office_name") or "Офис"
    user_name = context.get("user_name") or "Коллега"
    floor = context.get("room_floor")
    address = context.get("office_address")

    variants = {
        "BookingCreated": ("Бронирование подтверждено", "Ваша переговорная успешно забронирована.", "#176b5b"),
        "BookingUpdated": ("Бронирование изменено", "Изменения в бронировании успешно сохранены.", "#315c8a"),
        "BookingCancelled": ("Бронирование отменено", "Бронирование переговорной отменено.", "#8a4b45"),
    }
    title, lead, accent = variants.get(
        event_type,
        ("Уведомление о бронировании", "Статус вашего бронирования изменён.", "#176b5b"),
    )

    location_details = office_name
    if address:
        location_details += f" — {address}"
    room_details = room_name
    if floor is not None:
        room_details += f", {floor} этаж"

    message = EmailMessage()
    message["Subject"] = f"{title} — {room_name}"
    sender = EMAIL_FROM or "booking@meetingsystem.ru"
    message["From"] = formataddr((EMAIL_FROM_NAME, sender))
    message["To"] = recipient
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    sender_domain = sender.rsplit("@", 1)[-1] if "@" in sender else None
    message["Message-ID"] = make_msgid(domain=sender_domain)
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    message["Precedence"] = "bulk"

    message.set_content(f"""Здравствуйте, {user_name}!

{lead}

Офис: {location_details}
Переговорная: {room_details}
Начало: {start_time} (МСК)
Окончание: {end_time} (МСК)

С уважением,
команда Meeting Room Booking System

Это автоматическое уведомление. Отвечать на него не нужно.
""")

    safe = {key: escape(str(value)) for key, value in {
        "user_name": user_name,
        "title": title,
        "lead": lead,
        "office": location_details,
        "room": room_details,
        "start": start_time,
        "end": end_time,
    }.items()}
    message.add_alternative(f"""<!doctype html>
<html lang="ru"><body style="margin:0;background:#f3f6f4;font-family:Arial,sans-serif;color:#18312c">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f6f4;padding:32px 12px">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(25,55,48,.10)">
        <tr><td style="background:{accent};padding:28px 34px;color:#ffffff">
          <div style="font-size:13px;letter-spacing:1.4px;text-transform:uppercase;opacity:.82">Meeting Room Booking</div>
          <div style="font-size:26px;font-weight:700;margin-top:10px">{safe['title']}</div>
        </td></tr>
        <tr><td style="padding:32px 34px">
          <p style="font-size:17px;margin:0 0 14px">Здравствуйте, <strong>{safe['user_name']}</strong>!</p>
          <p style="font-size:16px;line-height:1.55;color:#52645f;margin:0 0 26px">{safe['lead']}</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f8f6;border:1px solid #e1e9e5;border-radius:14px">
            <tr><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;color:#6b7c77;font-size:13px;width:32%">Офис</td><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;font-weight:600">{safe['office']}</td></tr>
            <tr><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;color:#6b7c77;font-size:13px">Переговорная</td><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;font-weight:600">{safe['room']}</td></tr>
            <tr><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;color:#6b7c77;font-size:13px">Начало</td><td style="padding:16px 18px;border-bottom:1px solid #e1e9e5;font-weight:600">{safe['start']} <span style="color:#71817c;font-weight:400">МСК</span></td></tr>
            <tr><td style="padding:16px 18px;color:#6b7c77;font-size:13px">Окончание</td><td style="padding:16px 18px;font-weight:600">{safe['end']} <span style="color:#71817c;font-weight:400">МСК</span></td></tr>
          </table>
          <p style="font-size:15px;line-height:1.55;margin:26px 0 0">С уважением,<br><strong>команда Meeting Room Booking System</strong></p>
        </td></tr>
        <tr><td style="padding:18px 34px;background:#edf3f0;color:#71817c;font-size:12px;line-height:1.5">Это автоматическое уведомление. Отвечать на него не нужно.</td></tr>
      </table>
    </td></tr>
  </table>
</body></html>""", subtype="html")

    return message


def send_email(message):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM]):
        raise RuntimeError("SMTP settings are not configured")

    if SMTP_SECURITY == "ssl":
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)

    with smtp:
        if SMTP_SECURITY == "starttls":
            smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)


def send_email_via_unisender(message, event_id=None):
    if not UNISENDER_API_KEY or not EMAIL_FROM:
        raise RuntimeError("UniSender API settings are not configured")

    plain_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    payload = {
        "message": {
            "recipients": [{"email": str(message["To"])}],
            "body": {
                "plaintext": plain_part.get_content() if plain_part else "",
                "html": html_part.get_content() if html_part else "",
            },
            "subject": str(message["Subject"]),
            "from_email": EMAIL_FROM,
            "from_name": EMAIL_FROM_NAME,
            "track_links": 0,
            "track_read": 0,
            "skip_unsubscribe": 1,
        }
    }
    if event_id:
        payload["message"]["idempotence_key"] = str(event_id)

    api_request = urlrequest.Request(
        UNISENDER_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": UNISENDER_API_KEY,
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(api_request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"UniSender API returned HTTP {exc.code}: {details}") from exc
    if result.get("status") == "error":
        raise RuntimeError(f"UniSender API error: {result}")
    return result


def send_direct_notification(event):
    """Send through HTTPS on serverless deployments without breaking a booking."""
    if NOTIFICATION_DELIVERY != "unisender_api":
        return False

    try:
        context = get_booking_context(event.get("user_id"), event.get("room_id"))
        recipient = event.get("notification_email") or context.get("user_email")
        if not recipient:
            raise RuntimeError("Notification recipient is missing")
        message = build_email(event, recipient, context)
        send_email_via_unisender(message, event.get("event_id"))
        print(f"[EMAIL] UniSender notification sent: {recipient}")
        return True
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return False


def process_message(ch, method, properties, body):
    try:
        event = json.loads(body)

        print("\nПолучено сообщение:")
        print(json.dumps(event, indent=2, ensure_ascii=False))

        if event.get("simulate_failure") is True:
            raise RuntimeError("Simulated email sending failure")

        context = get_booking_context(event.get("user_id"), event.get("room_id"))
        recipient = event.get("notification_email")
        if not recipient:
            if not context.get("user_email"):
                raise RuntimeError("notification_email and user_id are missing in event")
            recipient = context["user_email"]

        message = build_email(event, recipient, context)
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
        queue=QUEUE_NAME,
        durable=True,
        arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE},
    )
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(
        exchange=DEAD_LETTER_EXCHANGE,
        queue=DEAD_LETTER_QUEUE,
        routing_key="#",
    )
    for routing_key in ROUTING_KEYS:
        channel.queue_bind(
            exchange=EXCHANGE_NAME,
            queue=QUEUE_NAME,
            routing_key=routing_key,
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
