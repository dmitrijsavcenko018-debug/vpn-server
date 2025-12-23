"""
Скрипт для синхронизации expire_at у VPN peer с подписками пользователей.

Находит peer'ы, у которых:
- is_active=true
- (expire_at IS NULL OR expire_at != subscription.expires_at)
- при наличии активной подписки пользователя

И обновляет expire_at = subscription.expires_at

Запуск:
  python -m app.scripts.sync_peer_expire_at          # dry-run режим (только показывает, что будет изменено)
  python -m app.scripts.sync_peer_expire_at --apply  # реальное обновление
"""

import asyncio
import argparse
import sys
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Добавляем путь к проекту
sys.path.insert(0, '/app')

from app.db import async_session
from app.models import User, Subscription, VpnPeer
from app.crud import get_active_subscription


async def sync_peer_expire_at(apply: bool = False) -> None:
    """
    Синхронизирует expire_at у peer'ов с подписками.
    
    Args:
        apply: Если True - реально обновляет БД, иначе только показывает что будет изменено
    """
    async with async_session() as session:
        # Находим все активные peer'ы
        result = await session.execute(
            select(VpnPeer)
            .where(VpnPeer.is_active == True)
            .options(selectinload(VpnPeer.user).selectinload(User.subscriptions))
        )
        peers = result.scalars().all()
        
        updates_needed = []
        
        for peer in peers:
            user = peer.user
            if not user:
                continue
            
            # Получаем активную подписку
            subscription = await get_active_subscription(session, user.id)
            if not subscription:
                continue
            
            # Проверяем, нужно ли обновление
            needs_update = False
            reason = None
            
            if peer.expire_at is None:
                needs_update = True
                reason = "expire_at is NULL"
            elif peer.expire_at != subscription.expires_at:
                needs_update = True
                reason = f"expire_at mismatch: peer={peer.expire_at}, sub={subscription.expires_at}"
            
            if needs_update:
                updates_needed.append({
                    'user_id': user.id,
                    'peer_id': peer.id,
                    'old_expire_at': peer.expire_at,
                    'new_expire_at': subscription.expires_at,
                    'subscription_id': subscription.id,
                    'reason': reason
                })
        
        # Выводим результаты
        if not updates_needed:
            print("✅ Все peer'ы синхронизированы. Обновлений не требуется.")
            return
        
        print(f"\n📊 Найдено {len(updates_needed)} peer'ов, требующих обновления:\n")
        for update in updates_needed:
            print(
                f"  user_id={update['user_id']}, peer_id={update['peer_id']}, " +
                f"subscription_id={update['subscription_id']}\n" +
                f"    Причина: {update['reason']}\n" +
                f"    Старое expire_at: {update['old_expire_at']}\n" +
                f"    Новое expire_at: {update['new_expire_at']}\n"
            )
        
        if not apply:
            print("\n⚠️  Это dry-run режим. Для реального обновления запустите с флагом --apply\n")
            return
        
        # Реальное обновление
        print(f"\n🔄 Применяю обновления...\n")
        updated_count = 0
        
        for update in updates_needed:
            try:
                # Получаем peer снова (для свежести данных)
                peer_result = await session.execute(
                    select(VpnPeer).where(VpnPeer.id == update['peer_id'])
                )
                peer = peer_result.scalar_one()
                
                old_expire_at = peer.expire_at
                peer.expire_at = update['new_expire_at']
                
                await session.commit()
                await session.refresh(peer)
                
                print(
                    f"✅ Обновлен peer_id={peer.id}, user_id={update['user_id']}: " +
                    f"{old_expire_at} -> {peer.expire_at}"
                )
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Ошибка при обновлении peer_id={update['peer_id']}: {e}")
                await session.rollback()
        
        print(f"\n✅ Обновлено {updated_count} из {len(updates_needed)} peer'ов.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Синхронизация expire_at у VPN peer с подписками"
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Реально применить изменения (по умолчанию - dry-run режим)'
    )
    
    args = parser.parse_args()
    
    asyncio.run(sync_peer_expire_at(apply=args.apply))


if __name__ == '__main__':
    main()
