import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..deps import get_session
from ..models import User, Subscription, VpnPeer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Schemas для ответов
class AdminStatsResponse(BaseModel):
    active_subs: int
    expired_24h: int
    revoked_24h: int
    expiring_24h: int


class ExpiringItem(BaseModel):
    user_id: int
    telegram_id: int
    subscription_id: int
    expires_at: str


class RevokedItem(BaseModel):
    peer_id: int
    user_id: int
    telegram_id: int
    revoked_at: str
    expire_at: Optional[str]


class AdminExpiringResponse(BaseModel):
    items: List[ExpiringItem]


class AdminRevokedResponse(BaseModel):
    items: List[RevokedItem]


class UserInfoResponse(BaseModel):
    user_id: int
    telegram_id: int
    subscription: Optional[dict]
    peer: Optional[dict]


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(session: AsyncSession = Depends(get_session)):
    """Получить статистику для админ-панели"""
    now = datetime.utcnow()
    yesterday = now - timedelta(hours=24)
    tomorrow = now + timedelta(hours=24)
    
    # Активные подписки
    active_result = await session.execute(
        select(func.count(Subscription.id))
        .where(Subscription.status == "active")
        .where(Subscription.expires_at > now)
    )
    active_subs = active_result.scalar() or 0
    
    # Истекшие за 24 часа
    expired_result = await session.execute(
        select(func.count(Subscription.id))
        .where(Subscription.expires_at <= now)
        .where(Subscription.expires_at > yesterday)
    )
    expired_24h = expired_result.scalar() or 0
    
    # Отключенные peer за 24 часа
    revoked_result = await session.execute(
        select(func.count(VpnPeer.id))
        .where(VpnPeer.revoked_at.isnot(None))
        .where(VpnPeer.revoked_at > yesterday)
        .where(VpnPeer.revoked_at <= now)
    )
    revoked_24h = revoked_result.scalar() or 0
    
    # Истекающие в ближайшие 24 часа
    expiring_result = await session.execute(
        select(func.count(Subscription.id))
        .where(Subscription.status == "active")
        .where(Subscription.expires_at <= tomorrow)
        .where(Subscription.expires_at > now)
    )
    expiring_24h = expiring_result.scalar() or 0
    
    return AdminStatsResponse(
        active_subs=active_subs,
        expired_24h=expired_24h,
        revoked_24h=revoked_24h,
        expiring_24h=expiring_24h
    )


@router.get("/expiring", response_model=AdminExpiringResponse)
async def get_expiring_subscriptions(session: AsyncSession = Depends(get_session)):
    """Получить список подписок, истекающих в ближайшие 24 часа (top 20)"""
    now = datetime.utcnow()
    tomorrow = now + timedelta(hours=24)
    
    result = await session.execute(
        select(User.id, User.telegram_id, Subscription.id, Subscription.expires_at)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Subscription.status == "active")
        .where(Subscription.expires_at <= tomorrow)
        .where(Subscription.expires_at > now)
        .order_by(Subscription.expires_at.asc())
        .limit(20)
    )
    
    items = []
    for row in result.all():
        items.append(ExpiringItem(
            user_id=row[0],
            telegram_id=row[1],
            subscription_id=row[2],
            expires_at=row[3].isoformat() if row[3] else ""
        ))
    
    return AdminExpiringResponse(items=items)


@router.get("/revoked", response_model=AdminRevokedResponse)
async def get_revoked_peers(session: AsyncSession = Depends(get_session)):
    """Получить список отключенных peer за последние 24 часа (top 20)"""
    now = datetime.utcnow()
    yesterday = now - timedelta(hours=24)
    
    result = await session.execute(
        select(VpnPeer.id, User.id, User.telegram_id, VpnPeer.revoked_at, VpnPeer.expire_at)
        .join(User, VpnPeer.user_id == User.id)
        .where(VpnPeer.revoked_at.isnot(None))
        .where(VpnPeer.revoked_at > yesterday)
        .where(VpnPeer.revoked_at <= now)
        .order_by(VpnPeer.revoked_at.desc())
        .limit(20)
    )
    
    items = []
    for row in result.all():
        items.append(RevokedItem(
            peer_id=row[0],
            user_id=row[1],
            telegram_id=row[2],
            revoked_at=row[3].isoformat() if row[3] else "",
            expire_at=row[4].isoformat() if row[4] else None
        ))
    
    return AdminRevokedResponse(items=items)


@router.get("/user/{telegram_id}", response_model=UserInfoResponse)
async def get_user_info(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """Получить информацию о пользователе по telegram_id"""
    user_result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем последнюю подписку
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    subscription = sub_result.scalar_one_or_none()
    
    # Получаем последний peer
    peer_result = await session.execute(
        select(VpnPeer)
        .where(VpnPeer.user_id == user.id)
        .order_by(VpnPeer.id.desc())
        .limit(1)
    )
    peer = peer_result.scalar_one_or_none()
    
    sub_dict = None
    if subscription:
        sub_dict = {
            "id": subscription.id,
            "status": subscription.status,
            "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None
        }
    
    peer_dict = None
    if peer:
        peer_dict = {
            "id": peer.id,
            "is_active": peer.is_active,
            "revoked_at": peer.revoked_at.isoformat() if peer.revoked_at else None,
            "expire_at": peer.expire_at.isoformat() if peer.expire_at else None
        }
    
    return UserInfoResponse(
        user_id=user.id,
        telegram_id=user.telegram_id,
        subscription=sub_dict,
        peer=peer_dict
    )

from .. import crud


class AdminActionResponse(BaseModel):
    ok: bool
    status: str
    peer_id: Optional[int] = None


@router.post("/user/{telegram_id}/disable", response_model=AdminActionResponse)
async def admin_disable_user(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """Отключить VPN для пользователя (отозвать активный peer)"""
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Находим активный peer: is_active=True AND revoked_at IS NULL
    peer_result = await session.execute(
        select(VpnPeer)
        .where(VpnPeer.user_id == user.id)
        .where(VpnPeer.is_active == True)
        .where(VpnPeer.revoked_at.is_(None))
        .order_by(VpnPeer.id.desc())
        .limit(1)
    )
    peer = peer_result.scalar_one_or_none()
    
    if not peer:
        return AdminActionResponse(ok=True, status="already_disabled")
    
    # Отзываем peer
    await crud.revoke_wireguard_peer(session, peer)
    await session.commit()
    
    return AdminActionResponse(ok=True, status="disabled", peer_id=peer.id)


@router.post("/user/{telegram_id}/enable", response_model=AdminActionResponse)
async def admin_enable_user(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """Включить VPN для пользователя (создать новый peer)"""
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем активную подписку
    now = datetime.utcnow()
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.status == "active")
        .where(Subscription.expires_at > now)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    subscription = sub_result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(status_code=400, detail="no active subscription")
    
    # Проверяем есть ли активный peer
    peer_result = await session.execute(
        select(VpnPeer)
        .where(VpnPeer.user_id == user.id)
        .where(VpnPeer.is_active == True)
        .where(VpnPeer.revoked_at.is_(None))
        .order_by(VpnPeer.id.desc())
        .limit(1)
    )
    peer = peer_result.scalar_one_or_none()
    
    if peer:
        return AdminActionResponse(ok=True, status="already_enabled", peer_id=peer.id)
    
    # Создаем новый peer
    new_peer = await crud.create_vpn_peer_for_user(session, user.id, expire_at=subscription.expires_at)
    await session.commit()
    
    return AdminActionResponse(ok=True, status="enabled", peer_id=new_peer.id)

class UserListItem(BaseModel):
    user_id: int
    telegram_id: int
    sub_status: str
    sub_expires_at: Optional[str]
    peer_id: Optional[int]
    peer_active: Optional[bool]
    peer_revoked_at: Optional[str]
    peer_expire_at: Optional[str]


class AdminUsersResponse(BaseModel):
    items: List[UserListItem]
    limit: int
    offset: int
    has_more: bool


@router.get("/users", response_model=AdminUsersResponse)
async def get_admin_users(
    limit: int = 15,
    offset: int = 0,
    session: AsyncSession = Depends(get_session)
):
    """Получить список пользователей с подписками и peer для админ-панели"""
    now = datetime.utcnow()
    
    # Получаем всех пользователей
    users_result = await session.execute(select(User).order_by(User.id.asc()))
    all_users = users_result.scalars().all()
    
    items_data = []
    for user in all_users:
        # Последняя подписка
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        subscription = sub_result.scalar_one_or_none()
        
        # Последний peer
        peer_result = await session.execute(
            select(VpnPeer)
            .where(VpnPeer.user_id == user.id)
            .order_by(VpnPeer.id.desc())
            .limit(1)
        )
        peer = peer_result.scalar_one_or_none()
        
        # Определяем статус подписки
        if not subscription:
            sub_status = "none"
            sub_expires_at = None
        elif subscription.expires_at and subscription.expires_at > now and subscription.status == "active":
            sub_status = "active"
            sub_expires_at = subscription.expires_at
        else:
            sub_status = "expired"
            sub_expires_at = subscription.expires_at if subscription else None
        
        items_data.append({
            "user": user,
            "sub_status": sub_status,
            "sub_expires_at": sub_expires_at,
            "peer": peer,
            "sort_priority": 0 if sub_status == "active" else (1 if sub_status == "expired" else 2),
            "sort_date": sub_expires_at if sub_expires_at else datetime.min
        })
    
    # Сортировка: active по expires_at ASC, expired по expires_at DESC, none внизу
    items_data.sort(key=lambda x: (
        x["sort_priority"],
        x["sort_date"].timestamp() if x["sub_status"] == "active" else -x["sort_date"].timestamp() if x["sub_expires_at"] else 0,
        x["user"].id
    ))
    
    # Пагинация
    paginated = items_data[offset:offset + limit + 1]
    has_more = len(paginated) > limit
    if has_more:
        paginated = paginated[:limit]
    
    items = []
    for item in paginated:
        user = item["user"]
        peer = item["peer"]
        items.append(UserListItem(
            user_id=user.id,
            telegram_id=user.telegram_id,
            sub_status=item["sub_status"],
            sub_expires_at=item["sub_expires_at"].isoformat() if item["sub_expires_at"] else None,
            peer_id=peer.id if peer else None,
            peer_active=peer.is_active if peer else None,
            peer_revoked_at=peer.revoked_at.isoformat() if peer and peer.revoked_at else None,
            peer_expire_at=peer.expire_at.isoformat() if peer and peer.expire_at else None
        ))
    
    return AdminUsersResponse(
        items=items,
        limit=limit,
        offset=offset,
        has_more=has_more
    )
