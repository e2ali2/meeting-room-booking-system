from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Office

router = APIRouter(prefix="/api/v1/offices", tags=["Offices"])


@router.get("")
def get_offices(db: Session = Depends(get_db)):
    offices = db.scalars(
        select(Office).where(Office.status == "ACTIVE")
    ).all()

    return [
        {
            "office_id": office.office_id,
            "name": office.name,
            "address": office.address,
            "status": office.status,
        }
        for office in offices
    ]