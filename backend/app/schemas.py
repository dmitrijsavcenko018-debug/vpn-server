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
    reminder_3days_sent: bool = False


class SubscriptionStatusResponse(BaseModel):
    status: str
    subscription: SubscriptionResponse | None = None


class SubscriptionStatusSimpleResponse(BaseModel):
    has_subscription: bool
    expires_at: str | None = None


class ActivateSubscriptionRequest(BaseModel):
    months: int


class VpnConfigResponse(BaseModel):
    config: str
    ip_address: str
    expires_at: str | None = None  # ISO формат даты окончания подписки
    config_url: str | None = None


class VpnPeerBase(BaseModel):
    user_id: int
    public_key: str
    private_key: str
    preshared_key: str | None = None
    address: str
    interface: str = "wg0"
    expire_at: datetime | None = None
    is_active: bool = True


class VpnPeerCreate(BaseModel):
    user_id: int
    expire_at: datetime | None = None


class VpnPeerRead(BaseModel):
    id: int
    user_id: int
    public_key: str
    private_key: str
    preshared_key: str | None = None
    address: str
    interface: str
    created_at: datetime
    expire_at: datetime | None = None
    revoked_at: datetime | None = None
    is_active: bool
