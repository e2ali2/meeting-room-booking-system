from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateBookingRequest(BaseModel):
    room_id: UUID
    start_time: datetime
    end_time: datetime


class UpdateBookingRequest(BaseModel):
    room_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

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