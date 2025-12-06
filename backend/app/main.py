from fastapi import FastAPI

from .routers import subscriptions, users, vpn


def create_app() -> FastAPI:
    app = FastAPI(title="VPN Subscription Service", version="0.1.0")
    app.include_router(users.router)
    app.include_router(subscriptions.router)
    app.include_router(vpn.router)
    return app


app = create_app()
