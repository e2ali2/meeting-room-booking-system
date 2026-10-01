from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, bookings, equipment, offices, rooms


app = FastAPI(
    title="Meeting Room Booking System API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in __import__("os").getenv(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


app.include_router(offices.router)
app.include_router(equipment.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(admin.router)

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    def frontend(request: Request, path: str = ""):
        host = request.headers.get("host", "").split(":", 1)[0].lower()
        if host in {"meetingsystem.ru", "www.meetingsystem.ru"}:
            target = "https://meeting-room-booking-system-two.vercel.app/"
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(target, status_code=307)
        return FileResponse(frontend_dir / "index.html")
