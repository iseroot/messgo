from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.application.services.auth_service import AuthService
from app.core.config import get_settings
from app.infrastructure.db import SessionLocal, init_db
from app.infrastructure.repositories import InviteRepository, SessionRepository, UserRepository
from app.presentation.routes import auth, chats, pages
from app.presentation.ws import endpoint as ws_endpoint


def create_app() -> FastAPI:
    """Фабрика FastAPI приложения."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
    app.state.templates = Jinja2Templates(directory=str(settings.templates_path))

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(chats.router)
    app.include_router(ws_endpoint.router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            service = AuthService(
                user_repo=UserRepository(db),
                invite_repo=InviteRepository(db),
                session_repo=SessionRepository(db),
            )
            service.ensure_bootstrap_invite(
                code=settings.bootstrap_invite_code,
                ttl_hours=settings.invite_default_ttl_hours,
                max_uses=settings.invite_default_limit,
            )
        finally:
            db.close()

    return app


app = create_app()
