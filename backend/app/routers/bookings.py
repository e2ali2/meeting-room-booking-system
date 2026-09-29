from datetime import datetime, timedelta, timezone
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, Office, OutboxEvent, Room, User
from app.schemas import CreateBookingRequest, UpdateBookingRequest

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


def get_current_user(db: Session) -> User:
    # Временная заглушка до подключения корпоративной авторизации.
    user = db.scalar(
        select(User).where(
            User.employee_id == "EMP-1001",
            User.role == "EMPLOYEE",
            User.status == "ACTIVE",
        )
    )

    if user is None:
        raise HTTPException(status_code=401, detail={
            "code": "UNAUTHORIZED",
            "message": "User is not authenticated",
        })

    return user


def validate_booking_time(start_time: datetime, end_time: datetime):
    now = datetime.now(timezone.utc)

    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Timezone is required",
        })

    if start_time <= now:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Booking cannot start in the past",
        })

    duration = end_time - start_time

    if duration < timedelta(minutes=15) or duration > timedelta(hours=4):
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Booking duration must be between 15 minutes and 4 hours",
        })

    if start_time.date() != end_time.date():
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Booking cannot cross a calendar day",
        })

    if end_time > now + timedelta(days=30):
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Booking cannot be created more than 30 days ahead",
        })

    if (
        start_time.minute % 15 != 0
        or end_time.minute % 15 != 0
        or start_time.second != 0
        or end_time.second != 0
    ):
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_BOOKING_TIME",
            "message": "Start and end time must use a 15-minute step",
        })


def check_room(db: Session, room_id: UUID):
    room = db.get(Room, room_id)

    if room is None:
        raise HTTPException(status_code=404, detail={
            "code": "ROOM_NOT_FOUND",
            "message": "Room not found",
        })

    if room.status != "ACTIVE":
        raise HTTPException(status_code=409, detail={
            "code": "ROOM_INACTIVE",
            "message": "Room is inactive",
        })

    office = db.get(Office, room.office_id)

    if office is None or office.status != "ACTIVE":
        raise HTTPException(status_code=409, detail={
            "code": "OFFICE_INACTIVE",
            "message": "Office is inactive",
        })


def check_conflict(
    db: Session,
    room_id: UUID,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: UUID | None = None,
):
    query = select(Booking).where(
        Booking.room_id == room_id,
        Booking.status == "ACTIVE",
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )

    if exclude_booking_id is not None:
        query = query.where(Booking.booking_id != exclude_booking_id)

    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail={
            "code": "ROOM_ALREADY_BOOKED",
            "message": "Room is already booked for the selected time",
        })


@router.post("", status_code=201)
def create_booking(
    request: CreateBookingRequest,
    db: Session = Depends(get_db),
):
    user = get_current_user(db)

    validate_booking_time(request.start_time, request.end_time)
    check_room(db, request.room_id)
    check_conflict(
        db,
        request.room_id,
        request.start_time,
        request.end_time,
    )

    booking = Booking(
        user_id=user.user_id,
        room_id=request.room_id,
        start_time=request.start_time,
        end_time=request.end_time,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        db.add(booking)

        # Получаем booking_id от PostgreSQL без COMMIT.
        db.flush()

        event_id = uuid.uuid4()

        outbox_event = OutboxEvent(
            event_id=event_id,
            aggregate_type="Booking",
            aggregate_id=booking.booking_id,
            event_type="BookingCreated",
            payload={
                "event_id": str(event_id),
                "event_type": "BookingCreated",
                "booking_id": str(booking.booking_id),
                "user_id": str(user.user_id),
                "room_id": str(request.room_id),
                "start_time": request.start_time.isoformat(),
                "end_time": request.end_time.isoformat(),
            },
            status="PENDING",
            retry_count=0,
            created_at=datetime.now(timezone.utc),
            published_at=None,
        )

        db.add(outbox_event)

        # Booking и OutboxEvent фиксируются одной транзакцией.
        db.commit()

    except IntegrityError as e:
        db.rollback()
        print("DATABASE INTEGRITY ERROR:", repr(e))
        raise HTTPException(status_code=409, detail={
            "code": "ROOM_ALREADY_BOOKED",
            "message": "Room is already booked for the selected time",
        })

    db.refresh(booking)
    return booking

@router.get("/my")
def get_my_bookings(db: Session = Depends(get_db)):
    user = get_current_user(db)

    return db.scalars(
        select(Booking)
        .where(Booking.user_id == user.user_id)
        .order_by(Booking.start_time)
    ).all()


@router.get("/{booking_id}")
def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    user = get_current_user(db)
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail={
            "code": "BOOKING_NOT_FOUND",
            "message": "Booking not found",
        })

    if booking.user_id != user.user_id and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN",
            "message": "Access denied",
        })

    return booking


@router.patch("/{booking_id}")
def update_booking(
    booking_id: UUID,
    request: UpdateBookingRequest,
    db: Session = Depends(get_db),
):
    user = get_current_user(db)
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail={
            "code": "BOOKING_NOT_FOUND",
            "message": "Booking not found",
        })

    if booking.user_id != user.user_id:
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN",
            "message": "Access denied",
        })
    if booking.status != "ACTIVE":
        raise HTTPException(status_code=409, detail={
            "code": "BOOKING_NOT_ACTIVE",
            "message": "Booking is not active",
        })
    now = datetime.now(timezone.utc)

    if booking.start_time - now < timedelta(minutes=30):
        raise HTTPException(status_code=409, detail={
            "code": "BOOKING_MODIFICATION_TOO_LATE",
            "message": "Booking can no longer be modified",
        })

    room_id = request.room_id or booking.room_id
    start_time = request.start_time or booking.start_time
    end_time = request.end_time or booking.end_time

    validate_booking_time(start_time, end_time)
    check_room(db, room_id)
    check_conflict(
        db,
        room_id,
        start_time,
        end_time,
        booking.booking_id,
    )

    booking.room_id = room_id
    booking.start_time = start_time
    booking.end_time = end_time
    booking.updated_at = now

    event_id = uuid.uuid4()

    outbox_event = OutboxEvent(
        event_id=event_id,
        aggregate_type="Booking",
        aggregate_id=booking.booking_id,
        event_type="BookingUpdated",
        payload={
            "event_id": str(event_id),
            "event_type": "BookingUpdated",
            "booking_id": str(booking.booking_id),
            "user_id": str(user.user_id),
            "room_id": str(room_id),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        status="PENDING",
        retry_count=0,
        created_at=now,
        published_at=None,
    )

    db.add(outbox_event)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "ROOM_ALREADY_BOOKED",
            "message": "Room is already booked for the selected time",
        })

    db.refresh(booking)
    return booking


@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    user = get_current_user(db)
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail={
            "code": "BOOKING_NOT_FOUND",
            "message": "Booking not found",
        })

    if booking.user_id != user.user_id:
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN",
            "message": "Access denied",
        })

    if booking.status != "ACTIVE":
        raise HTTPException(status_code=409, detail={
            "code": "BOOKING_NOT_ACTIVE",
            "message": "Booking is not active",
        })

    now = datetime.now(timezone.utc)

    if booking.start_time - now < timedelta(minutes=30):
        raise HTTPException(status_code=409, detail={
            "code": "BOOKING_CANCELLATION_TOO_LATE",
            "message": "Booking can no longer be cancelled",
        })

    booking.status = "CANCELLED"
    booking.cancelled_at = now
    booking.cancelled_by = user.user_id
    booking.updated_at = now

    event_id = uuid.uuid4()

    outbox_event = OutboxEvent(
        event_id=event_id,
        aggregate_type="Booking",
        aggregate_id=booking.booking_id,
        event_type="BookingCancelled",
        payload={
            "event_id": str(event_id),
            "event_type": "BookingCancelled",
            "booking_id": str(booking.booking_id),
            "user_id": str(user.user_id),
            "room_id": str(booking.room_id),
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "cancelled_at": now.isoformat(),
        },
        status="PENDING",
        retry_count=0,
        created_at=now,
        published_at=None,
    )

    db.add(outbox_event)
    db.commit()
    db.refresh(booking)

    return booking