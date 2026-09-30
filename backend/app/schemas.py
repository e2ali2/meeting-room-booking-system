from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, field_validator


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if len(normalized) > 320 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise ValueError("Enter a valid notification email")
    return normalized


class CreateBookingRequest(BaseModel):
    room_id: UUID
    start_time: datetime
    end_time: datetime
    notification_email: str | None = None

    _normalize_notification_email = field_validator("notification_email")(normalize_email)


class UpdateBookingRequest(BaseModel):
    room_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    notification_email: str | None = None

    _normalize_notification_email = field_validator("notification_email")(normalize_email)

class CreateOfficeRequest(BaseModel):
    name: str
    address: str
    status: str = "ACTIVE"


class UpdateOfficeRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    status: str | None = None


class CreateRoomRequest(BaseModel):
    office_id: UUID
    name: str
    floor: int
    capacity: int
    status: str = "ACTIVE"
    photo_url: str | None = None


class UpdateRoomRequest(BaseModel):
    office_id: UUID | None = None
    name: str | None = None
    floor: int | None = None
    capacity: int | None = None
    status: str | None = None
    photo_url: str | None = None


class CreateEquipmentRequest(BaseModel):
    name: str


class UpdateEquipmentRequest(BaseModel):
    name: str


class UpdateRoomEquipmentRequest(BaseModel):
    equipment_ids: list[UUID]
