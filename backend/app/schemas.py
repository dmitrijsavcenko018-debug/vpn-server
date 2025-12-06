from datetime import datetime

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    telegram_id: int


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    created_at: datetime


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    status: str
    plan: str
    started_at: datetime
    expires_at: datetime
    created_at: datetime


class SubscriptionStatusResponse(BaseModel):
    status: str
    subscription: SubscriptionResponse | None = None


class SubscriptionStatusSimpleResponse(BaseModel):
    has_subscription: bool
    expires_at: str | None = None


class ActivateSubscriptionRequest(BaseModel):
    months: int


class VpnConfigResponse(BaseModel):
    user_id: int
    peer_id: int
    address: str
    config: str
    config_url: str | None = None
    expires_at: str | None = None  # ISO формат даты окончания подписки
