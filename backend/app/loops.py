import asyncio
import os
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, func
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session
from .models import User, Subscription, VpnPeer
from .notifications import send_telegram_message
from . import crud

_last_admin_error_sent = {}

def _can_send_admin_error(key: str, every_seconds: int = 600) -> bool:
    """Проверяет, можно ли отправить админ-уведомление об ошибке (rate-limit)"""
    now = datetime.utcnow().timestamp()
    last = _last_admin_error_sent.get(key, 0)
    if now - last < every_seconds:
        return False
    _last_admin_error_sent[key] = now
    return True

logger = logging.getLogger(__name__)

def _renew_url() -> str | None:
    """Возвращает URL для deep-link продления подписки"""
    u = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    if not u:
        return None
    return f"https://t.me/{u}?start=renew"

def _renew_markup() -> dict | None:
    """Возвращает inline keyboard с кнопкой "Продлить" или None"""
    url = _renew_url()
    if not url:
        return None
    return {"inline_keyboard": [[{"text": "✅ Продлить", "url": url}]]}


async def monitor_and_fix_wg0_loop() -> None:
    """Временная безопасная заглушка"""
    tick = 0
    await asyncio.sleep(5)
    while True:
        try:
            tick += 1
            if tick % 10 == 0:
                logger.info("[monitor_and_fix_wg0_loop] noop (temporary)")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("[monitor_and_fix_wg0_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[monitor_and_fix_wg0_loop] error")
            await asyncio.sleep(60)

async def monitor_health_loop() -> None:
    """Временная безопасная заглушка"""
    tick = 0
    await asyncio.sleep(5)
    while True:
        try:
            tick += 1
            if tick % 10 == 0:
                logger.info("[monitor_health_loop] noop (temporary)")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("[monitor_health_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[monitor_health_loop] error")
            await asyncio.sleep(60)

async def notify_expiring_soon_loop() -> None:
    """Временная заглушка (старая логика "3 дня" отключена)"""
    await asyncio.sleep(5)
    while True:
        try:
            await asyncio.sleep(600)
        except asyncio.CancelledError:
            logger.info("[notify_expiring_soon_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[notify_expiring_soon_loop] error")
            await asyncio.sleep(600)

async def notify_expiring_subscriptions_24h_loop() -> None:
    """Уведомление пользователям за 24 часа до истечения подписки"""
    logger.info("[notify_expiring_subscriptions_24h_loop] Запуск фоновой задачи")
    await asyncio.sleep(5)
    
    while True:
        try:
            now = datetime.utcnow()
            window_end = now + timedelta(hours=24)

            async with async_session() as session:
                result = await session.execute(
                    select(Subscription)
                    .where(
                        Subscription.status == "active",
                        Subscription.expires_at > now,
                        Subscription.expires_at <= window_end
                    )
                )
                subs = result.scalars().all()

                for sub in subs:
                    try:
                        already_sent = await crud.check_notification_sent(session, sub.id, "expiring_24h")
                        if already_sent:
                            continue

                        user_result = await session.execute(
                            select(User).where(User.id == sub.user_id)
                        )
                        user = user_result.scalar_one_or_none()
                        if not user or not user.telegram_id:
                            continue

                        exp_str = sub.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                        text = "⏳ Ваша подписка скоро закончится.\nОкончание: " + exp_str + "\n\nОткройте бота и продлите подписку."

                        markup = _renew_markup()
                        ok = await send_telegram_message(user.telegram_id, text, reply_markup=markup)
                        if ok:
                            await crud.mark_notification_sent(session, user.id, sub.id, "expiring_24h")
                            # Админ-уведомление
                            if not crud.check_notification_sent(session, sub.id, "admin_expiring_24h"):
                                exp_str = sub.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                                admin_text = f"⚠️ Скоро окончание (24ч)\nuser_id={{user.id}}\ntg={{user.telegram_id}}\nsub_id={{sub.id}}\nexpires_at={{exp_str}}"
                                admin_ok = await send_admin_message(admin_text, reply_markup=_renew_markup())
                                if admin_ok:
                                    crud.mark_notification_sent(session, user.id, sub.id, "admin_expiring_24h")
                            logger.info("[notify_24h] sent user_id=%s sub_id=%s", user.id, sub.id)
                    except Exception as e:
                        logger.exception("[notify_24h] error sub_id=%s", getattr(sub, "id", None))

        except asyncio.CancelledError:
            logger.info("[notify_expiring_subscriptions_24h_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[notify_expiring_subscriptions_24h_loop] loop error")

        await asyncio.sleep(600)

async def disable_expired_vpn_peers_loop() -> None:
    """Отключение просроченных VPN-пиров и отправка уведомлений"""
    logger.info("[disable_expired_vpn_peers_loop] Запуск фоновой задачи")
    await asyncio.sleep(5)
    
    while True:
        try:
            now = datetime.utcnow()
            
            async with async_session() as session:
                result = await session.execute(
                    select(VpnPeer)
                    .where(
                        VpnPeer.is_active == True,
                        VpnPeer.expire_at.isnot(None),
                        VpnPeer.expire_at < now
                    )
                )
                peers = result.scalars().all()

                for peer in peers:
                    try:
                        # Отключение peer через существующую функцию
                        success = await crud.revoke_wireguard_peer(session, peer)
                        
                        if success:
                            # Уведомление expired_disabled после отключения
                            user_result = await session.execute(
                                select(User).where(User.id == peer.user_id)
                            )
                            user = user_result.scalar_one_or_none()
                            
                            if user and user.telegram_id:
                                sub_result = await session.execute(
                                    select(Subscription)
                                    .where(Subscription.user_id == user.id)
                                    .order_by(Subscription.expires_at.desc())
                                    .limit(1)
                                )
                                sub = sub_result.scalar_one_or_none()
                                
                                if sub:
                                    already_sent = await crud.check_notification_sent(session, sub.id, "expired_disabled")
                                    if not already_sent:
                                        text = "⛔️ Подписка закончилась, доступ к VPN отключён.\n\nЧтобы снова включить VPN — откройте бота и продлите подписку."
                                        markup = _renew_markup()
                                        ok = await send_telegram_message(user.telegram_id, text, reply_markup=markup)
                                        if ok:
                                            await crud.mark_notification_sent(session, user.id, sub.id, "expired_disabled")
                                            logger.info("[expired_disabled] sent user_id=%s sub_id=%s peer_id=%s", user.id, sub.id, peer.id)
                                        # Админ-уведомление
                                        if sub and not crud.check_notification_sent(session, sub.id, "admin_expired_disabled"):
                                            expire_str = peer.expire_at.strftime("%Y-%m-%d %H:%M:%S UTC") if peer.expire_at else "None"
                                            admin_text = f"⛔️ Отключён по сроку\nuser_id={{user.id}}\ntg={{user.telegram_id}}\npeer_id={{peer.id}}\nexpire_at={{expire_str}}\nsub_id={{sub.id}}"
                                            admin_ok = await send_admin_message(admin_text, reply_markup=_renew_markup())
                                            if admin_ok:
                                                crud.mark_notification_sent(session, user.id, sub.id, "admin_expired_disabled")
                    except Exception as e:
                        logger.exception("[disable_expired_vpn_peers_loop] error peer_id=%s", getattr(peer, "id", None))

        except asyncio.CancelledError:
            logger.info("[disable_expired_vpn_peers_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[disable_expired_vpn_peers_loop] loop error")

        await asyncio.sleep(300)

async def admin_daily_digest_loop() -> None:
    """Ежедневный дайджест для администратора (09:00 по серверному времени)"""
    import os
    from datetime import time
    
    logger.info("[admin_daily_digest_loop] Запуск фоновой задачи")
    await asyncio.sleep(5)
    
    while True:
        try:
            # Тестовый режим: если ADMIN_DIGEST_TEST_NOW=1, отправляем через 10 секунд
            test_mode = os.getenv("ADMIN_DIGEST_TEST_NOW", "").strip() == "1"
            if test_mode:
                logger.info("[admin_daily_digest_loop] ТЕСТОВЫЙ РЕЖИМ: дайджест через 10 секунд")
                await asyncio.sleep(10)
            else:
                # Вычисляем время до следующего 09:00
                now = datetime.utcnow()
                next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run = next_run.replace(day=next_run.day + 1)
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"[admin_daily_digest_loop] Следующий дайджест в {next_run} (через {wait_seconds:.0f} сек)")
                await asyncio.sleep(wait_seconds)
            
            # Сбор статистики
            now = datetime.utcnow()
            yesterday = now - timedelta(hours=24)
            
            async with async_session() as session:
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
                
                # Новые пользователи за 24 часа (если есть created_at)
                try:
                    new_users_result = await session.execute(
                        select(func.count(User.id))
                        .where(User.created_at > yesterday)
                        .where(User.created_at <= now)
                    )
                    new_users_24h = new_users_result.scalar() or 0
                except Exception as e:
                    logger.warning(f"[admin_daily_digest_loop] Поле created_at не найдено у users: {e}")
                    new_users_24h = "N/A"
                
                # Формируем текст
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                text = (
                    "📊 Дайджест за 24ч\n"
                    f"Активных подписок: {active_subs}\n"
                    f"Истекло подписок: {expired_24h}\n"
                    f"Отключено VPN (revoke): {revoked_24h}\n"
                    f"Новых пользователей: {new_users_24h}\n"
                    f"Время: {now_str} UTC"
                )
                # Отправляем админу
                ok = await send_admin_message(text)
                if ok:
                    logger.info(f"[admin_daily_digest_loop] Дайджест отправлен админу")
                else:
                    logger.warning("[admin_daily_digest_loop] Не удалось отправить дайджест админу")
                
                # В тестовом режиме выходим после первой отправки
                if test_mode:
                    logger.info("[admin_daily_digest_loop] ТЕСТОВЫЙ РЕЖИМ: завершение после отправки")
                    break
            
            if not test_mode:
                # Обычный режим: пересчитываем следующее время
                await asyncio.sleep(60)  # Небольшая задержка перед следующим расчетом
                
        except asyncio.CancelledError:
            logger.info("[admin_daily_digest_loop] cancelled")
            break
        except Exception as e:
            logger.exception("[admin_daily_digest_loop] error")
            try:
                await send_admin_message(f"🚨 Ошибка дайджеста: {str(e)}")
            except:
                pass
            # В случае ошибки ждём час перед повтором
            await asyncio.sleep(3600)

