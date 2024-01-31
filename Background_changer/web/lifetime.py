import logging
from typing import Awaitable, Callable

from fastapi import FastAPI
from Background_changer.settings import settings
from prometheus_fastapi_instrumentator.instrumentation import \
    PrometheusFastApiInstrumentator
from Background_changer.services.redis.lifetime import (init_redis,
                                                                   shutdown_redis)
from Background_changer.services.rabbit.lifetime import (init_rabbit,
                                                                    shutdown_rabbit)
from Background_changer.tkq import broker
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


def _setup_db(app: FastAPI) -> None:  # pragma: no cover
    """
    Creates connection to the database.

    This function creates SQLAlchemy engine instance,
    session_factory for creating sessions
    and stores them in the application's state property.

    :param app: fastAPI application.
    """
    engine = create_async_engine(str(settings.db_url), echo=settings.db_echo)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
def setup_prometheus(app: FastAPI) -> None:  # pragma: no cover
    """
    Enables prometheus integration.

    :param app: current application.
    """
    PrometheusFastApiInstrumentator(should_group_status_codes=False).instrument(
        app,
    ).expose(app, should_gzip=True, name="prometheus_metrics")


def register_startup_event(app: FastAPI) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: WPS430
        app.middleware_stack = None
        if not broker.is_worker_process:
            await broker.startup()
        _setup_db(app)
        init_redis(app)
        init_rabbit(app)
        setup_prometheus(app)
        app.middleware_stack = app.build_middleware_stack()
        pass  # noqa: WPS420

    return _startup


def register_shutdown_event(app: FastAPI) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """
    Actions to run on application's shutdown.

    :param app: fastAPI application.
    :return: function that actually performs actions.
    """

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: WPS430
        if not broker.is_worker_process:
            await broker.shutdown()
        await app.state.db_engine.dispose()
        
        await shutdown_redis(app)
        await shutdown_rabbit(app)
        pass  # noqa: WPS420

    return _shutdown