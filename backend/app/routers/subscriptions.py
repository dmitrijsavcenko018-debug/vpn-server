from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..deps import get_session

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/{telegram_id}", response_model=schemas.SubscriptionStatusSimpleResponse)
async def get_subscription_status(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    if not user:
        return schemas.SubscriptionStatusSimpleResponse(has_subscription=False, expires_at=None)
    
    subscription = await crud.get_active_subscription(session, user.id)
    if not subscription:
        return schemas.SubscriptionStatusSimpleResponse(has_subscription=False, expires_at=None)
    
    # Форматируем expires_at в ISO строку
    expires_at_str = subscription.expires_at.isoformat()
    return schemas.SubscriptionStatusSimpleResponse(
        has_subscription=True,
        expires_at=expires_at_str
    )


@router.post("/{telegram_id}/create-month", response_model=schemas.SubscriptionResponse)
async def create_month_subscription(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await crud.get_or_create_user(session, telegram_id)
    subscription = await crud.create_or_extend_month_subscription(session, user)
    if not subscription:
        raise HTTPException(status_code=500, detail="Unable to create subscription")
    return schemas.SubscriptionResponse.model_validate(subscription.__dict__, from_attributes=True)


@router.post("/{telegram_id}/activate", response_model=schemas.SubscriptionResponse)
async def activate_subscription(
    telegram_id: int,
    request: schemas.ActivateSubscriptionRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Активирует или продлевает подписку на указанное количество месяцев.
    Используется после успешной оплаты через Telegram Stars.
    При первой активации автоматически создает WireGuard peer и добавляет его на сервер.
    """
    if request.months not in [1, 3, 6, 12]:
        raise HTTPException(status_code=400, detail="Invalid number of months. Allowed values: 1, 3, 6, 12")
    
    user = await crud.get_or_create_user(session, telegram_id)
    
    # Проверяем, есть ли уже активный peer
    existing_peer = await crud.get_vpn_peer_by_user_id(session, user.id)
    is_new_subscription = not existing_peer
    
    # Активируем подписку
    subscription = await crud.activate_subscription_by_months(session, user, request.months)
    if not subscription:
        raise HTTPException(status_code=500, detail="Unable to activate subscription")
    
    # Если это новая подписка (peer еще не создан), создаем peer
    if is_new_subscription:
        try:
            # Используем expires_at из подписки для expire_at пира
            peer = await crud.create_vpn_peer_for_user(session, user.id, expire_at=subscription.expires_at)
            # Peer автоматически добавляется на WireGuard сервер в create_vpn_peer_for_user
        except ValueError as e:
            # Если у пользователя уже есть активный пир - возвращаем ошибку
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[activate_subscription] {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # Логируем ошибку, но не прерываем активацию подписки
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[activate_subscription] Ошибка при создании peer для user_id={user.id}: {e}")
    
    return schemas.SubscriptionResponse.model_validate(subscription.__dict__, from_attributes=True)


@router.post("/{telegram_id}/activate-test", response_model=schemas.SubscriptionResponse)
async def activate_test_subscription(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Активирует тестовый тариф на 24 часа.
    Используется после успешной оплаты тестового тарифа через Telegram Stars (1 Star).
    При первой активации автоматически создает WireGuard peer и добавляет его на сервер.
    """
    user = await crud.get_or_create_user(session, telegram_id)
    
    # Проверяем, есть ли уже активный peer
    existing_peer = await crud.get_vpn_peer_by_user_id(session, user.id)
    is_new_subscription = not existing_peer
    
    # Активируем тестовую подписку
    subscription = await crud.activate_test_subscription(session, user)
    if not subscription:
        raise HTTPException(status_code=500, detail="Unable to activate test subscription")
    
    # Если это новая подписка (peer еще не создан), создаем peer
    if is_new_subscription:
        try:
            # Используем expires_at из подписки для expire_at пира
            peer = await crud.create_vpn_peer_for_user(session, user.id, expire_at=subscription.expires_at)
            # Peer автоматически добавляется на WireGuard сервер в create_vpn_peer_for_user
        except ValueError as e:
            # Если у пользователя уже есть активный пир - возвращаем ошибку
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[activate_test_subscription] {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # Логируем ошибку, но не прерываем активацию подписки
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[activate_test_subscription] Ошибка при создании peer для user_id={user.id}: {e}")
    
    return schemas.SubscriptionResponse.model_validate(subscription.__dict__, from_attributes=True)
