from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Booking


def complete_expired_bookings(db: Session, now: datetime | None = None) -> int:
    """Persist completion before API reads/writes; cancelled bookings stay cancelled."""
    now = now or datetime.now(timezone.utc)
    result = db.execute(
        update(Booking)
        .where(Booking.status == "ACTIVE", Booking.end_time <= now)
        .values(status="COMPLETED", updated_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount
