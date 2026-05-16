from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import requests
from app.core.errors import ServiceError, service_error_handler
from app.core.settings import get_settings
from app.services.ai_config_service import get_ai_model_config
from app.services.model_warmup import warm_model


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.model_warmup = warm_model(get_settings())
        yield

    app = FastAPI(title="Agentic Request Parser API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ServiceError, service_error_handler)
    app.include_router(requests.router)
    app.state.model_warmup = {"status": "not_started"}

    @app.get("/api/health")
    def health():
        model_config = get_ai_model_config(get_settings())
        return {
            "status": "ok",
            "model_provider": model_config.provider,
            "model": model_config.model,
            "model_runtime": model_config.runtime,
            "api_key_configured": model_config.api_key_configured,
            "model_warmup": app.state.model_warmup,
        }

    return app


app = create_app()
