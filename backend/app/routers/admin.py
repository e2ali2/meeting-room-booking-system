from datetime import date, datetime, timezone
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.routers.bookings import check_conflict, check_room, validate_booking_time
from app.models import AuditLog, Booking, Equipment, Office, OutboxEvent, Room, RoomEquipment, User
from app.workers.email_worker import send_direct_notification
from app.schemas import (
    CreateEquipmentRequest,
    CreateOfficeRequest,
    CreateRoomRequest,
    UpdateBookingRequest,
    UpdateEquipmentRequest,
    UpdateOfficeRequest,
    UpdateRoomEquipmentRequest,
    UpdateRoomRequest,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def get_admin(db: Session, x_demo_role: str | None = None) -> User:
    return require_admin(db, x_demo_role)


def booking_to_dict(db: Session, booking: Booking):
    user = db.get(User, booking.user_id)
    room = db.get(Room, booking.room_id)
    office = db.get(Office, room.office_id) if room else None
    return {
        "booking_id": booking.booking_id,
        "user_id": booking.user_id,
        "room_id": booking.room_id,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "notification_email": booking.notification_email,
        "status": booking.status,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
        "cancelled_at": booking.cancelled_at,
        "cancelled_by": booking.cancelled_by,
        "owner": {"name": user.name, "email": user.email, "employee_id": user.employee_id} if user else None,
        "room": {"name": room.name, "floor": room.floor, "office_id": room.office_id} if room else None,
        "office": {"name": office.name} if office else None,
    }


def write_audit(
    db: Session,
    admin: User,
    action: str,
    booking_id: UUID | None = None,
    details: dict | None = None,
):
    audit = AuditLog(
        actor_user_id=admin.user_id,
        booking_id=booking_id,
        action=action,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)


@router.get("/bookings")
def get_all_bookings(
    status: str | None = Query(default=None),
    office_id: UUID | None = Query(default=None),
    booking_date: date | None = Query(default=None, alias="date"),
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    get_admin(db, x_demo_role)

    query = select(Booking)
    if status is not None:
        normalized_status = status.upper()
        if normalized_status not in {"ACTIVE", "CANCELLED", "COMPLETED"}:
            raise HTTPException(status_code=400, detail={
                "code": "INVALID_BOOKING_STATUS",
                "message": "Unknown booking status",
            })
        query = query.where(Booking.status == normalized_status)
    if office_id is not None:
        query = query.join(Room, Booking.room_id == Room.room_id).where(Room.office_id == office_id)
    if booking_date is not None:
        query = query.where(func.date(Booking.start_time) == booking_date)

    bookings = db.scalars(query.order_by(Booking.start_time.desc())).all()

    return [booking_to_dict(db, booking) for booking in bookings]


@router.patch("/bookings/{booking_id}")
def update_booking(
    booking_id: UUID,
    request: UpdateBookingRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BOOKING_NOT_FOUND",
                "message": "Booking not found",
            },
        )
    if booking.status != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BOOKING_NOT_ACTIVE",
                "message": "Booking is not active",
            },
        )
    if request.room_id is not None:
        room = db.get(Room, request.room_id)

        if room is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ROOM_NOT_FOUND",
                    "message": "Room not found",
                },
            )

        if room.status != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ROOM_INACTIVE",
                    "message": "Room is inactive",
                },
            )

        office = db.get(Office, room.office_id)

        if office is None or office.status != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OFFICE_INACTIVE",
                    "message": "Office is inactive",
                },
            )

    new_room_id = request.room_id or booking.room_id
    new_start = request.start_time or booking.start_time
    new_end = request.end_time or booking.end_time
    new_notification_email = request.notification_email or booking.notification_email

    validate_booking_time(new_start, new_end)

    conflict = db.execute(
        select(Booking).where(
            Booking.booking_id != booking.booking_id,
            Booking.room_id == new_room_id,
            Booking.status == "ACTIVE",
            Booking.start_time < new_end,
            Booking.end_time > new_start,
        )
    ).scalars().first()

    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ROOM_ALREADY_BOOKED",
                "message": "Room is already booked for the selected time",
            },
        )

    booking.room_id = new_room_id
    booking.start_time = new_start
    booking.end_time = new_end
    booking.notification_email = new_notification_email
    booking.updated_at = datetime.now(timezone.utc)

    event_id = uuid.uuid4()
    event_payload = {
        "event_id": str(event_id),
        "event_type": "BookingUpdated",
        "booking_id": str(booking.booking_id),
        "user_id": str(booking.user_id),
        "room_id": str(new_room_id),
        "start_time": new_start.isoformat(),
        "end_time": new_end.isoformat(),
        "notification_email": new_notification_email,
    }
    db.add(OutboxEvent(
        event_id=event_id,
        aggregate_type="Booking",
        aggregate_id=booking.booking_id,
        event_type="BookingUpdated",
        payload=event_payload,
        status="PENDING",
        retry_count=0,
        created_at=booking.updated_at,
        published_at=None,
    ))

    write_audit(
        db,
        admin,
        "ADMIN_BOOKING_UPDATED",
        booking.booking_id,
        {
            "room_id": str(booking.room_id),
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "notification_email": booking.notification_email,
        },
    )

    db.commit()
    db.refresh(booking)
    send_direct_notification(event_payload)

    return booking_to_dict(db, booking)


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: UUID,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BOOKING_NOT_FOUND",
                "message": "Booking not found",
            },
        )

    if booking.status == "CANCELLED":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BOOKING_ALREADY_CANCELLED",
                "message": "Booking is already cancelled",
            },
        )

    now = datetime.now(timezone.utc)

    booking.status = "CANCELLED"
    booking.cancelled_at = now
    booking.cancelled_by = admin.user_id
    booking.updated_at = now

    event_id = uuid.uuid4()
    event_payload = {
        "event_id": str(event_id),
        "event_type": "BookingCancelled",
        "booking_id": str(booking.booking_id),
        "user_id": str(booking.user_id),
        "room_id": str(booking.room_id),
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "cancelled_at": now.isoformat(),
        "notification_email": booking.notification_email,
    }
    db.add(OutboxEvent(
        event_id=event_id,
        aggregate_type="Booking",
        aggregate_id=booking.booking_id,
        event_type="BookingCancelled",
        payload=event_payload,
        status="PENDING",
        retry_count=0,
        created_at=now,
        published_at=None,
    ))

    write_audit(
        db,
        admin,
        "ADMIN_BOOKING_CANCELLED",
        booking.booking_id,
    )

    db.commit()
    db.refresh(booking)
    send_direct_notification(event_payload)

    return booking_to_dict(db, booking)


@router.get("/offices")
def get_all_offices(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    get_admin(db, x_demo_role)
    return db.scalars(select(Office).order_by(Office.name)).all()


@router.get("/rooms")
def get_all_rooms(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    get_admin(db, x_demo_role)
    rooms = db.scalars(select(Room).order_by(Room.name)).all()
    result = []
    for room in rooms:
        item = {column.name: getattr(room, column.name) for column in Room.__table__.columns}
        item["equipment_ids"] = list(db.scalars(select(RoomEquipment.equipment_id).where(RoomEquipment.room_id == room.room_id)).all())
        result.append(item)
    return result


@router.get("/equipment")
def get_all_equipment(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    get_admin(db, x_demo_role)
    return db.scalars(select(Equipment).order_by(Equipment.name)).all()


@router.get("/users")
def get_all_users(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    get_admin(db, x_demo_role)
    users = db.scalars(select(User).order_by(User.name)).all()
    return [{"user_id": u.user_id, "employee_id": u.employee_id, "name": u.name, "email": u.email, "role": u.role, "status": u.status} for u in users]


@router.post("/offices", status_code=201)
def create_office(
    request: CreateOfficeRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    office = Office(
        name=request.name,
        address=request.address,
        status=request.status,
    )

    db.add(office)
    db.flush()

    write_audit(
        db,
        admin,
        "ADMIN_OFFICE_CREATED",
        details={"office_id": str(office.office_id)},
    )

    db.commit()
    db.refresh(office)

    return office


@router.patch("/offices/{office_id}")
def update_office(
    office_id: UUID,
    request: UpdateOfficeRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    office = db.get(Office, office_id)

    if office is None:
        raise HTTPException(status_code=404, detail="Office not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(office, field, value)

    write_audit(
        db,
        admin,
        "ADMIN_OFFICE_UPDATED",
        details={"office_id": str(office.office_id)},
    )

    db.commit()
    db.refresh(office)

    return office


@router.post("/rooms", status_code=201)
def create_room(
    request: CreateRoomRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    office = db.get(Office, request.office_id)

    if office is None:
        raise HTTPException(status_code=404, detail="Office not found")

    room = Room(**request.model_dump())

    db.add(room)
    db.flush()

    write_audit(
        db,
        admin,
        "ADMIN_ROOM_CREATED",
        details={"room_id": str(room.room_id)},
    )

    db.commit()
    db.refresh(room)

    return room


@router.patch("/rooms/{room_id}")
def update_room(
    room_id: UUID,
    request: UpdateRoomRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    room = db.get(Room, room_id)

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(room, field, value)

    write_audit(
        db,
        admin,
        "ADMIN_ROOM_UPDATED",
        details={"room_id": str(room.room_id)},
    )

    db.commit()
    db.refresh(room)

    return room


@router.post("/equipment", status_code=201)
def create_equipment(
    request: CreateEquipmentRequest,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    db: Session = Depends(get_db),
):
    admin = get_admin(db, x_demo_role)

    equipment = Equipment(name=request.name)

    db.add(equipment)
    db.flush()

    write_audit(
        db,
        admin,
        "ADMIN_EQUIPMENT_CREATED",
        details={"equipment_id": str(equipment.equipment_id)},
    )

    db.commit()
    db.refresh(equipment)

    return equipment


@router.patch("/equipment/{equipment_id}")
def update_equipment(equipment_id: UUID, request: UpdateEquipmentRequest, x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    admin = get_admin(db, x_demo_role)
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    equipment.name = request.name
    write_audit(db, admin, "ADMIN_EQUIPMENT_UPDATED", details={"equipment_id": str(equipment_id)})
    db.commit()
    db.refresh(equipment)
    return equipment


@router.put("/rooms/{room_id}/equipment")
def update_room_equipment(room_id: UUID, request: UpdateRoomEquipmentRequest, x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    admin = get_admin(db, x_demo_role)
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    valid_ids = set(db.scalars(select(Equipment.equipment_id).where(Equipment.equipment_id.in_(request.equipment_ids))).all()) if request.equipment_ids else set()
    if len(valid_ids) != len(set(request.equipment_ids)):
        raise HTTPException(status_code=400, detail="Unknown equipment")
    for link in db.scalars(select(RoomEquipment).where(RoomEquipment.room_id == room_id)).all():
        db.delete(link)
    for equipment_id in valid_ids:
        db.add(RoomEquipment(room_id=room_id, equipment_id=equipment_id))
    write_audit(db, admin, "ADMIN_ROOM_EQUIPMENT_UPDATED", details={"room_id": str(room_id), "equipment_ids": [str(value) for value in valid_ids]})
    db.commit()
    return {"room_id": room_id, "equipment_ids": list(valid_ids)}


@router.get("/analytics/bookings")
def booking_analytics(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"), db: Session = Depends(get_db)):
    get_admin(db, x_demo_role)

    total = db.scalar(
        select(func.count()).select_from(Booking)
    )

    active = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.status == "ACTIVE")
    )

    cancelled = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.status == "CANCELLED")
    )

    completed = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.status == "COMPLETED")
    )

    now = datetime.now(timezone.utc)
    upcoming = db.scalar(select(func.count()).select_from(Booking).where(Booking.status == "ACTIVE", Booking.start_time >= now))
    today = db.scalar(select(func.count()).select_from(Booking).where(func.date(Booking.start_time) == now.date()))
    return {
        "total_bookings": total,
        "active_bookings": active,
        "cancelled_bookings": cancelled,
        "completed_bookings": completed,
        "upcoming_bookings": upcoming,
        "today_bookings": today,
    }
