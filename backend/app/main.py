from fastapi import FastAPI

from app.routers import bookings, equipment, offices, rooms


app = FastAPI(
    title="Meeting Room Booking System API",
    version="1.0.0",
)


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


app.include_router(offices.router)
app.include_router(equipment.router)
app.include_router(rooms.router)
app.include_router(bookings.router)