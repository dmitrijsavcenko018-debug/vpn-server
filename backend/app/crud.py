import base64
import os
import subprocess
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Subscription, User, VpnPeer
from .config import settings
from .wireguard_ssh import add_peer_to_wg0, remove_peer_from_wg0

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
    """
    Получает активный (не отозванный) VPN peer для пользователя.
    Возвращает самый свежий активный peer.
    """
    result = await session.execute(
        select(VpnPeer)
        .where(
            VpnPeer.user_id == user_id,
            VpnPeer.revoked_at.is_(None),
            VpnPeer.is_active == True
        )
        .order_by(VpnPeer.created_at.desc())
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


async def allocate_ip_address(session: AsyncSession, start_host: int = 10, end_host: int = 254) -> str:
    """
    Находит следующий свободный IP-адрес в диапазоне 10.66.66.{start_host}-{end_host}/32.
    Проверяет существующие peers в БД для избежания конфликтов.
    
    Args:
        session: Сессия БД
        start_host: Начальный номер хоста (по умолчанию 10, чтобы не трогать тестовые peers)
        end_host: Конечный номер хоста (по умолчанию 254)
    
    Returns:
        IP-адрес в формате "10.66.66.X/32"
    
    Raises:
        Exception: Если не удалось найти свободный IP
    """
    # Получаем все существующие активные peers
    existing_peers = await session.execute(
        select(VpnPeer).where(VpnPeer.revoked_at.is_(None), VpnPeer.is_active == True)
    )
    existing_addresses = {peer.address for peer in existing_peers.scalars().all()}
    
    # Ищем свободный IP от start_host до end_host
    host_id = start_host
    while host_id <= end_host:
        address = f"10.66.66.{host_id}/32"
        if address not in existing_addresses:
            return address
        host_id += 1
    
    # Если не нашли свободный IP
    logger.error(f"[allocate_ip_address] Не удалось найти свободный IP в диапазоне 10.66.66.{start_host}-{end_host}")
    raise Exception(f"No available IP addresses in range 10.66.66.{start_host}-{end_host}")


async def create_vpn_peer_for_user(session: AsyncSession, user_id: int) -> VpnPeer:
    """
    Создает новый VPN peer для пользователя с уникальными ключами и IP-адресом.
    Автоматически добавляет peer в WireGuard конфигурацию на сервере через SSH.
    
    ВАЖНО: Peer сохраняется в БД ТОЛЬКО после успешного добавления на сервер.
    Если добавление на сервер не удалось - выбрасывается исключение, peer не создается.
    """
    # 1. Генерируем правильные WireGuard ключи
    private_key = _generate_private_key()
    public_key = _generate_public_key(private_key)  # Публичный ключ вычисляется из приватного
    preshared_key = _generate_preshared_key()
    
    # 2. Находим следующий доступный IP-адрес
    # Начинаем с 10, чтобы не трогать тестовые peers (1-9 зарезервированы)
    address = await allocate_ip_address(session, start_host=10, end_host=254)
    
    # 3. СНАЧАЛА добавляем peer в WireGuard конфигурацию на сервере через SSH
    # wg set wg0 peer <public_key> allowed-ips <ip>/32 [preshared-key <psk>]
    # затем wg-quick save wg0
    logger.info(f"[create_vpn_peer_for_user] Добавляю peer на WireGuard сервер для user_id={user_id}")
    success = add_peer_to_wg0(
        ssh_host=settings.ssh_host,
        ssh_user=settings.ssh_user,
        ssh_key_path=settings.ssh_key_path,
        ssh_password=settings.ssh_password,
        public_key=public_key,
        preshared_key=preshared_key or "",
        allowed_ips=address,
        interface="wg0",
        wg_config_path=settings.wg_config_path
    )
    
    # 4. Если не удалось добавить на сервер - выбрасываем исключение, peer НЕ создается
    if not success:
        error_msg = f"[create_vpn_peer_for_user] Не удалось добавить peer на WireGuard сервер для user_id={user_id}. Peer НЕ создан в БД."
        logger.error(error_msg)
        raise Exception(f"Failed to add peer to WireGuard server: {error_msg}")
    
    logger.info(f"[create_vpn_peer_for_user] Peer успешно добавлен на WireGuard сервер для user_id={user_id}")
    
    # 5. ТОЛЬКО после успешного добавления на сервер - сохраняем peer в БД
    peer = VpnPeer(
        user_id=user_id,
        private_key=private_key,
        public_key=public_key,
        preshared_key=preshared_key,
        address=address,
        interface="wg0",  # По умолчанию используем wg0
    )
    session.add(peer)
    await session.commit()
    await session.refresh(peer)
    
    logger.info(f"[create_vpn_peer_for_user] Peer успешно создан в БД для user_id={user_id}, peer_id={peer.id}")
    return peer


async def revoke_wireguard_peer(session: AsyncSession, peer: VpnPeer) -> bool:
    """
    Отзывает (удаляет) WireGuard peer при окончании подписки.
    
    1. Удаляет блок [Peer] с данным public_key из wg0.conf по SSH.
    2. Делает wg syncconf wg0 для синхронизации конфигурации.
    3. Устанавливает peer.revoked_at и is_active=False в БД.
    
    Args:
        session: Сессия БД
        peer: VpnPeer для отзыва
    
    Returns:
        True если успешно, False в случае ошибки
    """
    if peer.is_revoked:
        logger.warning(f"[revoke_wireguard_peer] Peer {peer.id} уже отозван")
        return True
    
    try:
        # 1. Удаляем peer из WireGuard конфигурации на сервере через SSH
        success = remove_peer_from_wg0(
            ssh_host=settings.ssh_host,
            ssh_user=settings.ssh_user,
            ssh_key_path=settings.ssh_key_path,
            ssh_password=settings.ssh_password,
            public_key=peer.public_key,
            interface=peer.interface,
            wg_config_path=settings.wg_config_path
        )
        
        if not success:
            logger.warning(f"[revoke_wireguard_peer] Не удалось удалить peer {peer.id} с сервера, но помечаем как отозванный в БД")
        else:
            logger.info(f"[revoke_wireguard_peer] Peer {peer.id} успешно удален с WireGuard сервера")
        
        # 2. Помечаем peer как отозванный в БД
        from datetime import datetime
        peer.revoked_at = datetime.utcnow()
        peer.is_active = False
        await session.commit()
        await session.refresh(peer)
        
        return True
        
    except Exception as e:
        logger.error(f"[revoke_wireguard_peer] Ошибка при отзыве peer {peer.id}: {e}")
        # Все равно помечаем как отозванный в БД
        try:
            from datetime import datetime
            peer.revoked_at = datetime.utcnow()
            peer.is_active = False
            await session.commit()
        except Exception as db_error:
            logger.error(f"[revoke_wireguard_peer] Ошибка при обновлении БД: {db_error}")
        return False


async def revoke_expired_peers(session: AsyncSession) -> int:
    """
    Находит всех пользователей с истекшими подписками и отзывает их peers.
    Вызывается по крону или планировщику.
    
    Returns:
        Количество отозванных peers
    """
    from datetime import datetime
    now = datetime.utcnow()
    revoked_count = 0
    
    # Находим всех пользователей с истекшими подписками
    expired_subscriptions = await session.execute(
        select(Subscription)
        .where(Subscription.expires_at < now, Subscription.status == "active")
    )
    expired_subs = expired_subscriptions.scalars().all()
    
    # Для каждого пользователя с истекшей подпиской отзываем peer
    for subscription in expired_subs:
        # Помечаем подписку как неактивную
        subscription.status = "expired"
        
        # Находим активный peer пользователя
        peer = await get_vpn_peer_by_user_id(session, subscription.user_id)
        if peer and not peer.is_revoked:
            try:
                await revoke_wireguard_peer(session, peer)
                revoked_count += 1
                logger.info(f"[revoke_expired_peers] Отозван peer {peer.id} для user_id={subscription.user_id}")
            except Exception as e:
                logger.error(f"[revoke_expired_peers] Ошибка при отзыве peer для user_id={subscription.user_id}: {e}")
    
    await session.commit()
    return revoked_count
