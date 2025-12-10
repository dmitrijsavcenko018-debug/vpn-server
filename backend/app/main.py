import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import async_session
from .routers import subscriptions, users, vpn
from .tasks import disable_expired_vpn_peers_loop, monitor_and_fix_wg0_loop, monitor_health_loop, notify_expiring_soon_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Запускает фоновые задачи при старте и корректно останавливает их при завершении.
    """
    # Запускаем фоновые задачи
    task_disable_expired = asyncio.create_task(disable_expired_vpn_peers_loop())
    task_notify_expiring = asyncio.create_task(notify_expiring_soon_loop())
    task_monitor_health = asyncio.create_task(monitor_health_loop(async_session))
    task_monitor_wg = asyncio.create_task(monitor_and_fix_wg0_loop())
    
    yield
    
    # Останавливаем задачи при завершении приложения
    task_disable_expired.cancel()
    task_notify_expiring.cancel()
    task_monitor_health.cancel()
    task_monitor_wg.cancel()
    try:
        await task_disable_expired
    except asyncio.CancelledError:
        pass
    try:
        await task_notify_expiring
    except asyncio.CancelledError:
        pass
    try:
        await task_monitor_health
    except asyncio.CancelledError:
        pass
    try:
        await task_monitor_wg
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="VPN Subscription Service", version="0.1.0", lifespan=lifespan)
    app.include_router(users.router)
    app.include_router(subscriptions.router)
    app.include_router(vpn.router)
    return app


app = create_app()
