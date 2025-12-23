import asyncio
import logging
import subprocess
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import crud
from .db import async_session
from .models import Subscription, VpnPeer
from .notifications import send_admin_alert, send_telegram_message

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def disable_expired_vpn_peers_loop() -> None:
    """
    Фоновая задача, которая периодически проверяет и отключает просроченные VPN-пиры.
    Проверка выполняется каждые 5 минут.
    """
    logger.info("[disable_expired_vpn_peers_loop] Запуск фоновой задачи для отключения просроченных VPN-пиров")
    
    while True:
        try:
            
            logger.info("[disable_expired_vpn_peers_loop] Начало проверки просроченных VPN-пиров")
            now = datetime.utcnow()
            
            # Создаем новую сессию для этой итерации
            async with async_session() as session:
                # Находим все просроченные активные пиры
                result = await session.execute(
                    select(VpnPeer).where(
                        VpnPeer.expire_at.isnot(None),
                        VpnPeer.expire_at < now,
                        VpnPeer.is_active == True
                    )
                )
                expired_peers = result.scalars().all()
                
                if expired_peers:
                    logger.info(f"[disable_expired_vpn_peers_loop] Найдено {len(expired_peers)} просроченных VPN-пиров")
                    
                    for peer in expired_peers:
                        try:
                            logger.info(
                                f"[disable_expired_vpn_peers_loop] Отключение просроченного peer_id={peer.id}, "
                                f"user_id={peer.user_id}, expire_at={peer.expire_at}"
                            )
                            # Используем существующую функцию отключения пира
                            success = await crud.revoke_wireguard_peer(session, peer)
                            if success:
                                # Уведомление пользователю после отключения
                                try:
                                    from .models import User, Subscription
                                    user_result = await session.execute(select(User).where(User.id == peer.user_id))
                                    user = user_result.scalar_one_or_none()
                                    if user and user.telegram_id:
                                        sub_result = await session.execute(
                                            select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.expires_at.desc()).limit(1)
                                        )
                                        sub = sub_result.scalar_one_or_none()
                                        if sub:
                                            already_sent = await crud.check_notification_sent(session, sub.id, "expired_disabled")
                                            if not already_sent:
                                                text = "⛔️ Подписка закончилась, доступ к VPN отключён.\n\nЧтобы снова включить VPN — откройте бота и продлите подписку."
                                                ok = await send_telegram_message(user.telegram_id, text)
                                                if ok:
                                                    await crud.mark_notification_sent(session, user.id, sub.id, "expired_disabled")
                                                    logger.info(f"[disable_expired_vpn_peers_loop] expired_disabled sent: user_id={user.id} peer_id={peer.id}")
                                except Exception as notify_error:
                                    logger.exception(f"[disable_expired_vpn_peers_loop] error sending expired_disabled notify")
                            if success:
                                logger.info(f"[disable_expired_vpn_peers_loop] Peer {peer.id} успешно отключен")
                            else:
                                logger.warning(f"[disable_expired_vpn_peers_loop] Не удалось отключить peer {peer.id}")
                        except Exception as e:
                            logger.error(
                                f"[disable_expired_vpn_peers_loop] Ошибка при отключении peer {peer.id}: {e}",
                                exc_info=True
                            )
                            # Продолжаем обработку других пиров даже при ошибке
                else:
                    logger.debug("[disable_expired_vpn_peers_loop] Просроченных VPN-пиров не найдено")
            
            # Пауза 5 минут (300 секунд) перед следующей проверкой
            await asyncio.sleep(300)
                    
        except asyncio.CancelledError:
            logger.info("[disable_expired_vpn_peers_loop] Задача отменена")
            break
        except Exception as e:
            logger.error(
                f"[disable_expired_vpn_peers_loop] Критическая ошибка в фоновой задаче: {e}",
                exc_info=True
            )
            # Пауза перед следующей попыткой, чтобы не зациклиться при постоянных ошибках
            await asyncio.sleep(60)


async def notify_expiring_soon_loop() -> None:
    """
    Фоновая задача, которая периодически проверяет подписки, истекающие через 3 дня,
    и отправляет пользователям уведомления в Telegram.
    Проверка выполняется каждый час.
    """
    logger.info("[notify_expiring_soon_loop] Запуск фоновой задачи для отправки напоминаний об истечении подписки")
    
    while True:
        try:
            # Пауза 1 час (3600 секунд) перед первой проверкой
            await asyncio.sleep(3600)
            
            logger.debug("[notify_expiring_soon_loop] Начало проверки подписок, истекающих через 3 дня")
            now = datetime.utcnow()
            
            # Вычисляем диапазон: от now + 3 дня до now + 3 дня + 1 день (в пределах суток)
            target_date_start = now + timedelta(days=3)
            target_date_end = now + timedelta(days=4)
            
            # Создаем новую сессию для этой итерации
            async with async_session() as session:
                # Находим все активные подписки, которые истекают через ~3 дня
                # и напоминание еще не отправлено
                from sqlalchemy.orm import selectinload
                
                result = await session.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.user))
                    .where(
                        Subscription.expires_at >= target_date_start,
                        Subscription.expires_at < target_date_end,
                        Subscription.status == "active",
                        Subscription.reminder_3days_sent == False
                    )
                )
                expiring_subscriptions = result.scalars().all()
                
                if expiring_subscriptions:
                    logger.info(
                        f"[notify_expiring_soon_loop] Найдено {len(expiring_subscriptions)} подписок, "
                        f"истекающих через 3 дня"
                    )
                    
                    for subscription in expiring_subscriptions:
                        try:
                            # Получаем пользователя (уже загружен через selectinload)
                            user = subscription.user
                            
                            if not user:
                                logger.warning(
                                    f"[notify_expiring_soon_loop] Не найден пользователь для subscription_id={subscription.id}"
                                )
                                continue
                            
                            telegram_id = user.telegram_id
                            
                            # Формируем текст сообщения
                            message_text = (
                                f"🔔 <b>Напоминание о подписке</b>\n\n"
                                f"Ваш доступ к VPN заканчивается <b>через 3 дня</b> ({expires_date_str}).\n\n"
                                f"Чтобы продолжить пользоваться VPN, не забудьте продлить подписку!"
                            )
"

"
                                f"Ваш доступ к VPN заканчивается <b>через 3 дня</b> ({expires_date_str}).

"
                                f"Чтобы продолжить пользоваться VPN, не забудьте продлить подписку!"
                            )
                            
                            logger.info(
                                f"[notify_expiring_soon_loop] Отправка напоминания subscription_id={subscription.id}, "
                                f"user_id={user.id}, telegram_id={telegram_id}, expires_at={subscription.expires_at}"
                            )
                            
                            # Отправляем уведомление
                            await send_telegram_message(telegram_id, message_text)
                            
                            # Помечаем, что напоминание отправлено
                            subscription.reminder_3days_sent = True
                            await session.commit()
                            
                            logger.info(
                                f"[notify_expiring_soon_loop] Напоминание успешно отправлено и помечено "
                                f"subscription_id={subscription.id}"
                            )
                            
                        except ValueError as e:
                            # Ошибка с токеном бота - логируем, но продолжаем
                            logger.error(
                                f"[notify_expiring_soon_loop] Ошибка при отправке напоминания subscription_id={subscription.id}: {e}"
                            )
                            # Не помечаем как отправленное, чтобы попробовать еще раз
                        except Exception as e:
                            logger.error(
                                f"[notify_expiring_soon_loop] Ошибка при отправке напоминания subscription_id={subscription.id}: {e}",
                                exc_info=True
                            )
                            # Не помечаем как отправленное, чтобы попробовать еще раз
                            # Откатываем изменения для этой подписки
                            await session.rollback()
                            # Продолжаем обработку других подписок
                else:
                    logger.debug("[notify_expiring_soon_loop] Подписок для напоминания не найдено")
                    
        except asyncio.CancelledError:
            logger.info("[notify_expiring_soon_loop] Задача отменена")
            break
        except Exception as e:
            logger.error(
                f"[notify_expiring_soon_loop] Критическая ошибка в фоновой задаче: {e}",
                exc_info=True
            )
            # Пауза перед следующей попыткой, чтобы не зациклиться при постоянных ошибками
            await asyncio.sleep(3600)


def _check_wireguard_health() -> tuple[bool, str]:
    """
    Проверяет состояние WireGuard интерфейса wg0.
    
    Returns:
        tuple[bool, str]: (is_healthy, error_message)
        - is_healthy: True если WireGuard работает нормально, False если есть проблема
        - error_message: Сообщение об ошибке (если is_healthy == False) или пустая строка
    """
    try:
        # Проверяем существование интерфейса wg0
        result = subprocess.run(
            ["wg", "show", "wg0"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Неизвестная ошибка"
            return False, f"WireGuard wg0 недоступен: {error_msg}"
        
        # Проверяем, что вывод не пустой (интерфейс существует и активен)
        if not result.stdout.strip():
            return False, "WireGuard wg0 не активен или пуст"
        
        # Проверяем, что в выводе есть информация об интерфейсе
        if "interface: wg0" not in result.stdout.lower() and "public key" not in result.stdout.lower():
            return False, "WireGuard wg0 имеет некорректную конфигурацию"
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "Таймаут при проверке WireGuard wg0"
    except FileNotFoundError:
        return False, "Команда 'wg' не найдена. Проверьте установку wireguard-tools"
    except Exception as e:
        return False, f"Неожиданная ошибка при проверке WireGuard: {str(e)}"



from .notifications import send_telegram_message

logger = logging.getLogger(__name__)


async def notify_expiring_subscriptions_24h_loop() -> None:
    """
    Фоновая задача, которая периодически проверяет подписки, истекающие через 24 часа,
    и отправляет пользователям уведомления в Telegram.
    Проверка выполняется каждые 10 минут.
    """
    logger.info("[notify_expiring_subscriptions_24h_loop] Запуск фоновой задачи для отправки уведомлений за 24 часа до истечения")
    
    while True:
        try:
            # Пауза 10 минут (600 секунд) перед первой проверкой
            await asyncio.sleep(600)
            
            logger.debug("[notify_expiring_subscriptions_24h_loop] Начало проверки подписок, истекающих через 24 часа")
            now = datetime.utcnow()
            
            # Вычисляем диапазон: от now + 23h 50min до now + 24h 10min (окно 20 минут для надежности)
            target_date_start = now + timedelta(hours=23, minutes=50)
            target_date_end = now + timedelta(hours=24, minutes=10)
            
            # Создаем новую сессию для этой итерации
            async with async_session() as session:
                # Находим все активные подписки, которые истекают через ~24 часа
                result = await session.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.user))
                    .where(
                        Subscription.expires_at >= target_date_start,
                        Subscription.expires_at < target_date_end,
                        Subscription.status == "active"
                    )
                )
                expiring_subscriptions = result.scalars().all()
                
                if expiring_subscriptions:
                    logger.info(
                        f"[notify_expiring_subscriptions_24h_loop] Найдено {len(expiring_subscriptions)} подписок, "
                        f"истекающих через 24 часа"
                    )
                    
                    for subscription in expiring_subscriptions:
                        try:
                            # Проверяем, не отправляли ли уже уведомление
                            already_sent = await crud.check_notification_sent(session, subscription.id, "expiring_24h")
                            if already_sent:
                                logger.debug(
                                    f"[notify_expiring_subscriptions_24h_loop] Уведомление expiring_24h уже отправлено для subscription_id={subscription.id}"
                                )
                                continue
                            
                            # Получаем пользователя (уже загружен через selectinload)
                            user = subscription.user
                            
                            if not user:
                                logger.warning(
                                    f"[notify_expiring_subscriptions_24h_loop] Не найден пользователь для subscription_id={subscription.id}"
                                )
                                continue
                            
                            telegram_id = user.telegram_id
                            
                            # Формируем текст сообщения
                            message_text = (
                                f"⏳ <b>Подписка скоро закончится</b>\n\n"
                                f"Окончание: {expires_date_str}\n"
                                f"Нажмите «Продлить» в боте."
                            )
                                f"Окончание: {expires_date_str}
"
                                f"Нажмите «Продлить» в боте."
                            )
                            
                            logger.info(
                                f"[notify_expiring_subscriptions_24h_loop] Отправка уведомления expiring_24h: "
                                f"subscription_id={subscription.id}, user_id={user.id}, telegram_id={telegram_id}, expires_at={subscription.expires_at}"
                            )
                            
                            # Отправляем уведомление
                            success = await send_telegram_message(telegram_id, message_text)
                            
                            if success:
                                # Помечаем, что уведомление отправлено
                                await crud.mark_notification_sent(session, user.id, subscription.id, "expiring_24h")
                                logger.info(
                                    f"[notify_expiring_subscriptions_24h_loop] Уведомление expiring_24h успешно отправлено и помечено "
                                    f"subscription_id={subscription.id}"
                                )
                            else:
                                logger.warning(
                                    f"[notify_expiring_subscriptions_24h_loop] Не удалось отправить уведомление expiring_24h "
                                    f"subscription_id={subscription.id}, telegram_id={telegram_id}"
                                )
                                # Не помечаем как отправленное, чтобы попробовать еще раз позже
                                
                        except Exception as e:
                            logger.error(
                                f"[notify_expiring_subscriptions_24h_loop] Ошибка при обработке subscription_id={subscription.id}: {e}",
                                exc_info=True
                            )
                            # Продолжаем обработку других подписок
                else:
                    logger.debug("[notify_expiring_subscriptions_24h_loop] Подписок для уведомления не найдено")
                    
        except asyncio.CancelledError:
            logger.info("[notify_expiring_subscriptions_24h_loop] Задача отменена")
            break
        except Exception as e:
            logger.error(
                f"[notify_expiring_subscriptions_24h_loop] Критическая ошибка в фоновой задаче: {e}",
                exc_info=True
            )
            # Пауза перед следующей попыткой

async def monitor_health_loop(session_maker: async_sessionmaker[AsyncSession]) -> None:
    """
    Фоновая задача для мониторинга здоровья системы (БД и WireGuard).
    Проверка выполняется каждые 60 секунд.
    
    Args:
        session_maker: Session maker для создания асинхронных сессий БД
    """
    logger.info("[monitor_health_loop] Запуск фоновой задачи мониторинга здоровья системы")
    
    # Флаги для отслеживания состояния (чтобы не спамить при повторных ошибках)
    db_last_error_time: datetime | None = None
    wg_last_error_time: datetime | None = None
    error_cooldown = timedelta(minutes=5)  # Отправляем алерт не чаще раза в 5 минут для той же ошибки
    
    while True:
        try:
            # 1. Проверка БД
            try:
                async with session_maker() as session:
                    # Выполняем простой запрос для проверки подключения
                    await session.execute(text("SELECT 1"))
                    await session.commit()
                    
                    # Если дошли сюда - БД работает
                    if db_last_error_time:
                        # БД восстановилась после ошибки
                        logger.info("[monitor_health_loop] БД восстановлена после ошибки")
                        await send_admin_alert("✅ <b>БД восстановлена</b>

База данных снова доступна.")
                        db_last_error_time = None
                    
                    logger.debug("[monitor_health_loop] Проверка БД: OK")
                    
            except Exception as db_error:
                now = datetime.utcnow()
                
                # Отправляем алерт только если прошло достаточно времени с последней ошибки
                if not db_last_error_time or (now - db_last_error_time) > error_cooldown:
                    error_msg = f"❌ <b>Ошибка БД</b>

База данных недоступна:
<code>{str(db_error)}</code>"
                    logger.error(f"[monitor_health_loop] Ошибка проверки БД: {db_error}", exc_info=True)
                    await send_admin_alert(error_msg)
                    db_last_error_time = now
            
            # 2. Проверка WireGuard
            wg_healthy, wg_error = _check_wireguard_health()
            
            if not wg_healthy:
                now = datetime.utcnow()
                
                # Отправляем алерт только если прошло достаточно времени с последней ошибки
                if not wg_last_error_time or (now - wg_last_error_time) > error_cooldown:
                    error_msg = f"❌ <b>Ошибка WireGuard</b>

WireGuard wg0 недоступен:
<code>{wg_error}</code>"
                    logger.error(f"[monitor_health_loop] Ошибка проверки WireGuard: {wg_error}")
                    await send_admin_alert(error_msg)
                    wg_last_error_time = now
            else:
                # WireGuard работает нормально
                if wg_last_error_time:
                    # WireGuard восстановился после ошибки
                    logger.info("[monitor_health_loop] WireGuard восстановлен после ошибки")
                    await send_admin_alert("✅ <b>WireGuard восстановлен</b>

Интерфейс wg0 снова доступен.")
                    wg_last_error_time = None
                
                logger.debug("[monitor_health_loop] Проверка WireGuard: OK")
            
        except asyncio.CancelledError:
            logger.info("[monitor_health_loop] Задача отменена")
            break
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"❌ <b>monitor_health_loop: ошибка</b>

Тип ошибки: <code>{error_type}</code>
Сообщение: <code>{str(e)}</code>"
            logger.error(
                f"[monitor_health_loop] Критическая ошибка в фоновой задаче мониторинга: {e}",
                exc_info=True
            )
            await send_admin_alert(error_msg)
        
        # Пауза между проверками: 60 секунд
        await asyncio.sleep(60)


async def monitor_and_fix_wg0_loop() -> None:
    """
    Фоновая задача для проверки и авто-фикса WireGuard интерфейса wg0.
    Если wg0 недоступен, пытается поднять его через wg-quick up wg0
    и отправляет уведомление администратору.
    """
    logger.info("[monitor_and_fix_wg0_loop] Запуск фоновой задачи мониторинга wg0")

    # Флаг, чтобы не слать уведомления слишком часто при постоянной ошибке
    last_fail_time: datetime | None = None
    error_cooldown = timedelta(minutes=5)

    while True:
        try:
            # Проверяем состояние wg0
            result = subprocess.run(
                ["wg", "show", "wg0"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            wg_ok = result.returncode == 0 and result.stdout.strip()

            if wg_ok:
                # Если ранее было падение — считаем, что восстановилось
                if last_fail_time:
                    logger.info("[monitor_and_fix_wg0_loop] wg0 в норме после ошибки")
                    await send_admin_alert("✅ wg0 работает корректно после восстановления")
                    last_fail_time = None
            else:
                now = datetime.utcnow()
                stderr_msg = result.stderr.strip() if result.stderr else "wg0 недоступен"
                logger.warning(f"[monitor_and_fix_wg0_loop] wg0 неактивен: {stderr_msg}")

                # Пытаемся поднять wg0
                try:
                    subprocess.run(
                        ["wg-quick", "up", "wg0"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=True,
                    )
                    logger.info("[monitor_and_fix_wg0_loop] wg0 перезапущен автоматически")
                    await send_admin_alert("⚠️ wg0 был неактивен, интерфейс перезапущен автоматически")
                    last_fail_time = None
                except subprocess.CalledProcessError as e:
                    err_text = e.stderr.strip() if e.stderr else str(e)
                    logger.error(f"[monitor_and_fix_wg0_loop] Не удалось перезапустить wg0: {err_text}")
                    if (not last_fail_time) or (now - last_fail_time > error_cooldown):
                        await send_admin_alert(f"❌ Не удалось перезапустить wg0: {err_text}")
                        last_fail_time = now
                except Exception as e:
                    logger.exception(f"[monitor_and_fix_wg0_loop] Ошибка при попытке перезапуска wg0: {e}")
                    if (not last_fail_time) or (now - last_fail_time > error_cooldown):
                        await send_admin_alert(f"❌ Не удалось перезапустить wg0: {e}")
                        last_fail_time = now

        except asyncio.CancelledError:
            logger.info("[monitor_and_fix_wg0_loop] Задача отменена")
            break
        except Exception as e:
            logger.exception(f"[monitor_and_fix_wg0_loop] Критическая ошибка: {e}")
            now = datetime.utcnow()
            if (not last_fail_time) or (now - last_fail_time > error_cooldown):
                await send_admin_alert(f"❌ monitor_and_fix_wg0_loop: {e}")
                last_fail_time = now

        await asyncio.sleep(60)

