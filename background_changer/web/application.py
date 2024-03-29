import logging
import os
from importlib import metadata

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import UJSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.staticfiles import StaticFiles

from background_changer.logging import configure_logging
from background_changer.settings import settings
from background_changer.web.api.router import api_router
from background_changer.web.lifetime import (
    register_shutdown_event,
    register_startup_event,
)


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    configure_logging()
    if settings.sentry_dsn:
        # Enables sentry integration.
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_sample_rate,
            environment=settings.environment,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                LoggingIntegration(
                    level=logging.getLevelName(
                        settings.log_level.value,
                    ),
                    event_level=logging.ERROR,
                ),
                SqlalchemyIntegration(),
            ],
        )
    app = FastAPI(
        title="background_changer",
        version=metadata.version("background_changer"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
    )

    if not os.path.exists(settings.DEFAULT_MEDIA_PATH):
        os.makedirs(settings.DEFAULT_MEDIA_PATH)
    if not os.path.exists(settings.DEFAULT_BACKGROUND_PATH):
        os.makedirs(settings.DEFAULT_BACKGROUND_PATH)
    if not os.path.exists(settings.DEFAULT_IMAGES_PATH):
        os.makedirs(settings.DEFAULT_IMAGES_PATH)
    app.mount(
        "/media",
        StaticFiles(directory=settings.DEFAULT_MEDIA_PATH),
        name="media",
    )
    # Adds startup and shutdown events.
    register_startup_event(app)
    register_shutdown_event(app)

    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    return app
