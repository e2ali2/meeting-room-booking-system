import os

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_demo_user(
    db: Session,
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
) -> User:
    """Temporary demo identity adapter.

    The rest of the application depends on a resolved User, so this function can
    later be replaced by a corporate OIDC/JWT adapter without changing business
    services or database rules.
    """
    if os.getenv("DEMO_AUTH_ENABLED", "true").lower() != "true":
        raise HTTPException(status_code=401, detail={
            "code": "CORPORATE_AUTH_REQUIRED",
            "message": "Demo authentication is disabled",
        })

    role = (x_demo_role or "EMPLOYEE").upper()
    if role not in {"EMPLOYEE", "ADMIN"}:
        raise HTTPException(status_code=401, detail={
            "code": "INVALID_DEMO_ROLE",
            "message": "Unknown demo role",
        })

    query = select(User).where(User.role == role, User.status == "ACTIVE")
    if role == "EMPLOYEE":
        employee_id = os.getenv("DEMO_EMPLOYEE_ID")
        if employee_id:
            query = query.where(User.employee_id == employee_id)
        else:
            # Older local databases used EMP-1001 while seed.sql uses EMP1001.
            query = query.where(User.employee_id.in_(["EMP-1001", "EMP1001"]))

    user = db.scalars(query).first()
    if user is None:
        raise HTTPException(status_code=401, detail={
            "code": "DEMO_USER_NOT_FOUND",
            "message": f"Active demo {role.lower()} user was not found",
        })
    return user


def require_admin(db: Session, x_demo_role: str | None) -> User:
    user = get_demo_user(db, x_demo_role)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN",
            "message": "Administrator access is required",
        })
    return user
