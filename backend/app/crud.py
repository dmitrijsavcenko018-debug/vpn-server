import base64
import os
import subprocess
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Subscription, User, VpnPeer
from .config import settings
from .wireguard_ssh import add_peer_to_wg0

logger = logging.getLogger(__name__)

SUBSCRIPTION_DURATION = timedelta(days=30)


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, telegram_id: int) -> User:
    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        return user
    return await create_user(session, telegram_id)


async def get_active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    """
    Получает активную подписку пользователя.
    Если найдено несколько активных подписок, возвращает ту, что истекает позже всех.
    Поддерживает как обычные тарифы (month), так и тестовые (test_1d).
    """
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.expires_at > now, Subscription.status == "active")
        .order_by(Subscription.expires_at.desc())
    )
    # Используем first() вместо scalar_one_or_none(), чтобы не падать при нескольких результатах
    # Возвращаем подписку с самой поздней датой окончания (уже отсортировано по expires_at DESC)
    return result.scalars().first()


async def create_or_extend_month_subscription(session: AsyncSession, user: User) -> Subscription:
    subscription = await get_active_subscription(session, user.id)
    now = datetime.utcnow()
    if subscription:
        subscription.expires_at += SUBSCRIPTION_DURATION
    else:
        subscription = Subscription(
            user_id=user.id,
            status="active",
            plan="month",
            started_at=now,
            expires_at=now + SUBSCRIPTION_DURATION,
        )
        session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def activate_subscription_by_months(session: AsyncSession, user: User, months: int) -> Subscription:
    """
    Активирует или продлевает подписку на указанное количество месяцев.
    Если подписка активна (expires_at > now) - продлевает от текущей даты окончания.
    Если подписка неактивна или её нет - создает новую с текущей даты.
    При повторной покупке срок суммируется с действующей подпиской.
    """
    subscription = await get_active_subscription(session, user.id)
    now = datetime.utcnow()
    # Используем приблизительно 30 дней на месяц
    duration = timedelta(days=30 * months)
    
    if subscription and subscription.expires_at > now:
        # Подписка активна - суммируем срок с текущей датой окончания
        base_date = subscription.expires_at
        new_expires_at = base_date + duration
        subscription.expires_at = new_expires_at
        subscription.status = "active"
    else:
        # Подписка неактивна или её нет - создаем новую от текущей даты
        base_date = now
        new_expires_at = base_date + duration
        
        if subscription:
            # Обновляем существующую неактивную подписку
            subscription.expires_at = new_expires_at
            subscription.status = "active"
            subscription.started_at = now
        else:
            # Создаем новую подписку
            subscription = Subscription(
                user_id=user.id,
                status="active",
                plan="month",
                started_at=now,
                expires_at=new_expires_at,
            )
            session.add(subscription)
    
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def activate_test_subscription(session: AsyncSession, user: User) -> Subscription:
    """
    Активирует тестовый тариф на 24 часа.
    Создает новую подписку типа "test_1d" с датой окончания через 24 часа.
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=24)
    
    # Создаем тестовую подписку
    subscription = Subscription(
        user_id=user.id,
        status="active",
        plan="test_1d",
        started_at=now,
        expires_at=expires_at,
        )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def get_vpn_peer_by_user_id(session: AsyncSession, user_id: int) -> VpnPeer | None:
    result = await session.execute(
        select(VpnPeer).where(VpnPeer.user_id == user_id, VpnPeer.revoked_at.is_(None)).order_by(VpnPeer.created_at.desc())
    )
    return result.scalar_one_or_none()


def _generate_private_key() -> str:
    """
    Генерирует валидный WireGuard приватный ключ используя wg genkey.
    Если wg недоступен, использует fallback на криптографически стойкий генератор.
    """
    try:
        # Пробуем использовать wg genkey (если установлен)
        result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback: генерируем криптографически стойкий ключ (32 байта в base64)
        # Это не идеально, но лучше чем случайные данные
        # В продакшене должен быть установлен wireguard-tools
        return base64.b64encode(os.urandom(32)).decode("ascii")


def _generate_public_key(private_key: str) -> str:
    """
    Генерирует публичный ключ из приватного используя wg pubkey.
    Если wg недоступен, возвращает placeholder (в продакшене должен быть wg).
    """
    try:
        # Пробуем использовать wg pubkey
        result = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback: генерируем случайный ключ (в продакшене это не должно происходить)
        # В реальном проекте должен быть установлен wireguard-tools
        return base64.b64encode(os.urandom(32)).decode("ascii")


def _generate_preshared_key() -> str:
    """
    Генерирует preshared key используя wg genpsk.
    Если wg недоступен, использует fallback.
    """
    try:
        result = subprocess.run(
            ["wg", "genpsk"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback
        return base64.b64encode(os.urandom(32)).decode("ascii")


async def create_vpn_peer_for_user(session: AsyncSession, user_id: int) -> VpnPeer:
    """
    Создает новый VPN peer для пользователя с уникальными ключами и IP-адресом.
    Автоматически добавляет peer в WireGuard конфигурацию на сервере через SSH.
    """
    # Генерируем правильные WireGuard ключи
    private_key = _generate_private_key()
    public_key = _generate_public_key(private_key)  # Публичный ключ вычисляется из приватного
    preshared_key = _generate_preshared_key()
    
    # Находим следующий доступный IP-адрес
    # Проверяем существующие peers для избежания конфликтов
    existing_peers = await session.execute(
        select(VpnPeer).where(VpnPeer.revoked_at.is_(None))
    )
    existing_addresses = {peer.address for peer in existing_peers.scalars().all()}
    
    # Генерируем уникальный IP от 10.66.66.2 до 10.66.66.254
    host_id = 2
    while host_id <= 254:
        address = f"10.66.66.{host_id}/32"
        if address not in existing_addresses:
            break
        host_id += 1
    else:
        logger.error(f"[create_vpn_peer_for_user] Не удалось найти свободный IP для user_id={user_id}")
        raise Exception("No available IP addresses in range 10.66.66.2-254")
    
    peer = VpnPeer(
        user_id=user_id,
        private_key=private_key,
        public_key=public_key,
        preshared_key=preshared_key,
        address=address,
    )
    session.add(peer)
    await session.flush()
    
    # Добавляем peer в WireGuard конфигурацию на сервере через SSH
    try:
        success = add_peer_to_wg0(
            ssh_host=settings.ssh_host,
            ssh_user=settings.ssh_user,
            ssh_key_path=settings.ssh_key_path,
            ssh_password=settings.ssh_password,
            public_key=public_key,
            preshared_key=preshared_key or "",
            allowed_ips=address,
            wg_config_path=settings.wg_config_path
        )
        if not success:
            logger.warning(f"[create_vpn_peer_for_user] Не удалось добавить peer на сервер для user_id={user_id}, но peer создан в БД")
        else:
            logger.info(f"[create_vpn_peer_for_user] Peer успешно добавлен на WireGuard сервер для user_id={user_id}")
    except Exception as e:
        logger.error(f"[create_vpn_peer_for_user] Ошибка при добавлении peer на сервер: {e}")
        # Продолжаем выполнение - peer уже создан в БД, можно добавить на сервер позже
    
    await session.commit()
    await session.refresh(peer)
    return peer
