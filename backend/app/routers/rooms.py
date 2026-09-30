from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, Equipment, Office, Room, RoomEquipment
from app.routers.bookings import validate_booking_time

router = APIRouter(prefix="/api/v1/rooms", tags=["Rooms"])


def room_to_dict(db: Session, room: Room):
    equipment = db.execute(
        select(Equipment.equipment_id, Equipment.name)
        .join(RoomEquipment, Equipment.equipment_id == RoomEquipment.equipment_id)
        .where(RoomEquipment.room_id == room.room_id)
        .order_by(Equipment.name)
    ).all()
    return {
        "room_id": room.room_id,
        "office_id": room.office_id,
        "name": room.name,
        "floor": room.floor,
        "capacity": room.capacity,
        "status": room.status,
        "photo_url": room.photo_url,
        "equipment": [{"equipment_id": item.equipment_id, "name": item.name} for item in equipment],
    }


@router.get("")
def get_rooms(db: Session = Depends(get_db)):
    rooms = db.scalars(
        select(Room).where(Room.status == "ACTIVE")
    ).all()

    return [room_to_dict(db, room) for room in rooms]


@router.get("/available")
def get_available_rooms(
    office_id: UUID,
    start_time: datetime,
    end_time: datetime,
    min_capacity: int | None = None,
    equipment: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_booking_time(start_time, end_time)

    query = (
        select(Room)
        .join(Office, Room.office_id == Office.office_id)
        .where(
            Room.office_id == office_id,
            Room.status == "ACTIVE",
            Office.status == "ACTIVE",
        )
    )

    if min_capacity is not None:
        query = query.where(Room.capacity >= min_capacity)
    if equipment:
        for equipment_name in equipment:
            equipment_room_ids = (
                select(RoomEquipment.room_id)
                .join(
                    Equipment,
                    RoomEquipment.equipment_id == Equipment.equipment_id,
                )
                .where(Equipment.name == equipment_name)
            )

            query = query.where(Room.room_id.in_(equipment_room_ids))
    busy_rooms = select(Booking.room_id).where(
        Booking.status == "ACTIVE",
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )

    query = query.where(Room.room_id.not_in(busy_rooms))

    return [room_to_dict(db, room) for room in db.scalars(query).all()]
