import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.runs import ApiError, RunService
from app.config import Settings, get_settings
from app.negotiation.dot import DotError

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, runs: RunService | None = None
) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(title="anthrobbic API")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.state.runs = runs or RunService(settings)
    application.include_router(router)

    @application.exception_handler(ApiError)
    def api_error(_: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(status_code=error.status, content={"detail": error.detail})

    @application.exception_handler(DotError)
    def data_error(_: Request, error: DotError) -> JSONResponse:
        logger.error("flight data unavailable: %s", error)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The flight dataset is not available. Set FLIGHTS_CSV on "
                "the API to the DOT flights file."
            },
        )

    return application


app = create_app()
