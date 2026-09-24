from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.admin.routers.identity_link_router import router as identity_link_router
from src.api.v1.admin.routers.ingestion_router import router as ingestion_router
from src.api.v1.auth.routers.auth_router import router as auth_router
from src.api.v1.chat.routers.conversation_router import router as conversation_router
from src.api.v1.chat.routers.live_router import router as live_router
from src.api.v1.matches.routers.match_router import router as match_router
from src.api.v1.national_teams.routers.national_team_router import (
    router as national_team_router,
)
from src.api.v1.players.routers.player_router import router as player_router
from src.config import app_settings

SHOW_DOCS_IN = {"local", "staging"}

API_V1_ROUTERS = (
    auth_router,
    live_router,
    conversation_router,
    national_team_router,
    match_router,
    player_router,
    ingestion_router,
    identity_link_router,
)


def create_app() -> FastAPI:
    app_kwargs: dict = {"title": "World Cup AI Scout API"}
    if app_settings.ENVIRONMENT not in SHOW_DOCS_IN:
        app_kwargs["openapi_url"] = None

    app = FastAPI(**app_kwargs)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in API_V1_ROUTERS:
        app.include_router(router, prefix="/api/v1")

    @app.get("/health", tags=["health"], summary="Liveness check")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
