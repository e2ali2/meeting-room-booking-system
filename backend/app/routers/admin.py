from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.bookings import validate_booking_time
from app.models import AuditLog, Booking, Equipment, Office, Room, User
from app.schemas import (
    CreateEquipmentRequest,
    CreateOfficeRequest,
    CreateRoomRequest,
    UpdateBookingRequest,
    UpdateOfficeRequest,
    UpdateRoomRequest,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def get_admin(db: Session) -> User:
    admin = db.execute(
        select(User).where(
            User.role == "ADMIN",
            User.status == "ACTIVE",
        )
    ).scalars().first()

    if admin is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Active administrator not found",
            },
        )

    return admin


def booking_to_dict(booking: Booking):
    return {
        "booking_id": booking.booking_id,
        "user_id": booking.user_id,
        "room_id": booking.room_id,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "status": booking.status,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
        "cancelled_at": booking.cancelled_at,
        "cancelled_by": booking.cancelled_by,
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
def get_all_bookings(db: Session = Depends(get_db)):
    get_admin(db)

    bookings = db.execute(
        select(Booking).order_by(Booking.start_time.desc())
    ).scalars().all()

    return [booking_to_dict(booking) for booking in bookings]


@router.patch("/bookings/{booking_id}")
def update_booking(
    booking_id: UUID,
    request: UpdateBookingRequest,
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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
    booking.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        admin,
        "ADMIN_BOOKING_UPDATED",
        booking.booking_id,
        {
            "room_id": str(booking.room_id),
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
        },
    )

    db.commit()
    db.refresh(booking)

    return booking_to_dict(booking)


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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

    write_audit(
        db,
        admin,
        "ADMIN_BOOKING_CANCELLED",
        booking.booking_id,
    )

    db.commit()
    db.refresh(booking)

    return booking_to_dict(booking)


@router.post("/offices", status_code=201)
def create_office(
    request: CreateOfficeRequest,
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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
    db: Session = Depends(get_db),
):
    admin = get_admin(db)

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


@router.get("/analytics/bookings")
def booking_analytics(db: Session = Depends(get_db)):
    get_admin(db)

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

    return {
        "total_bookings": total,
        "active_bookings": active,
        "cancelled_bookings": cancelled,
        "completed_bookings": completed,
    }