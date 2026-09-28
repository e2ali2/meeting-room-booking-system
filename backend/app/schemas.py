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