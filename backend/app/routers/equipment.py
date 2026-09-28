from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Equipment

router = APIRouter(prefix="/api/v1/equipment", tags=["Equipment"])


@router.get("")
def get_equipment(db: Session = Depends(get_db)):
    equipment = db.scalars(select(Equipment)).all()

    return [
        {
            "equipment_id": item.equipment_id,
            "name": item.name,
        }
        for item in equipment
    ]