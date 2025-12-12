import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..config import settings
from ..deps import get_session

router = APIRouter(prefix="/api/vpn", tags=["vpn"])


def _render_config(private_key: str, address: str, preshared_key: str | None = None) -> str:
    """
    Генерирует WireGuard конфиг для клиента ТОЛЬКО из данных БД.
    Включает AllowedIPs и PersistentKeepalive для корректной работы VPN.
    
    Args:
        private_key: Приватный ключ клиента из БД
        address: IP адрес клиента из БД (например, 10.66.66.10/32)
        preshared_key: Preshared ключ из БД (опционально)
    """
    # Очищаем ключи от пробелов и переносов строк
    private_key = private_key.strip()
    if preshared_key:
        preshared_key = preshared_key.strip()
    
    # Убеждаемся, что address содержит /32
    address = address.strip()
    if not address.endswith("/32"):
        if "/" in address:
            # Если есть другой префикс, заменяем на /32
            address = address.split("/")[0] + "/32"
        else:
            # Если нет префикса, добавляем /32
            address = address + "/32"
    
    # Формируем конфиг с правильным форматированием
    config_lines = [
        "[Interface]",
        f"PrivateKey = {private_key}",
        f"Address = {address}",
        "DNS = 1.1.1.1",
        "",
        "[Peer]",
        f"PublicKey = {settings.wg_public_key.strip()}",
    ]
    
    # Добавляем PresharedKey только если он есть в БД
    if preshared_key:
        config_lines.append(f"PresharedKey = {preshared_key}")
    
    config_lines.extend([
        f"Endpoint = {settings.wg_host.strip()}:{settings.wg_port}",
        "AllowedIPs = 0.0.0.0/0, ::/0",
        "PersistentKeepalive = 25",
    ])
    
    # Объединяем строки с переносами
    config = "\n".join(config_lines) + "\n"
    
    return config


@router.get("/config/{telegram_id}", response_model=schemas.VpnConfigResponse)
async def get_vpn_config(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """
    Получает VPN-конфиг для пользователя по telegram_id.
    Требует наличия активной подписки (включая тестовый тариф test_1d).
    """
    try:
        # 1. Проверяем наличие пользователя
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 2. Проверяем наличие активной подписки (поддерживает test_1d и обычные тарифы)
        subscription = await crud.get_active_subscription(session, user.id)
        if not subscription:
            # Если подписка истекла, отзываем peer (если есть)
            peer_to_revoke = await crud.get_vpn_peer_by_user_id(session, user.id)
            if peer_to_revoke and not peer_to_revoke.is_revoked:
                try:
                    await crud.revoke_wireguard_peer(session, peer_to_revoke)
                except Exception as e:
                    print(f"[get_vpn_config] Ошибка при отзыве peer для истекшей подписки: {e}")
            raise HTTPException(status_code=403, detail="Active subscription required")
        
        # 3. Получаем или создаем VPN peer
        # ВАЖНО: create_vpn_peer_for_user добавляет peer на сервер через wg set + wg-quick save
        # Peer сохраняется в БД ТОЛЬКО после успешного добавления на сервер
        # Если добавление не удалось - выбрасывается исключение, конфиг НЕ выдается
        peer = await crud.get_vpn_peer_by_user_id(session, user.id)
        if not peer:
            try:
                # Создает peer: генерирует ключи → wg set wg0 peer ... → wg-quick save wg0 → сохраняет в БД
                # Используем expires_at из подписки для expire_at пира
                peer = await crud.create_vpn_peer_for_user(session, user.id, expire_at=subscription.expires_at)
                # Коммитим peer в БД
                await session.commit()
                await session.refresh(peer)
            except ValueError as e:
                # Если у пользователя уже есть активный пир - возвращаем понятную ошибку
                raise HTTPException(
                    status_code=400,
                    detail=str(e)
                )
            except Exception as e:
                # Если не удалось добавить peer на сервер - конфиг НЕ выдаем
                print(f"[get_vpn_config] Ошибка при создании VPN peer для user_id={user.id}:")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create VPN peer configuration"
                )
        
        # 4. Проверяем, что у peer есть необходимые данные
        # Если peer в БД - значит он уже успешно добавлен на сервер
        if not peer.private_key or not peer.address:
            raise HTTPException(
                status_code=500,
                detail="VPN peer configuration is incomplete"
            )
        
        # 5. Генерируем конфиг ТОЛЬКО из данных БД
        # Peer уже добавлен на сервер, можно безопасно выдавать конфиг
        try:
            config_text = _render_config(
                private_key=peer.private_key,
                address=peer.address,
                preshared_key=peer.preshared_key
            )
        except Exception as e:
            print(f"[get_vpn_config] Ошибка при генерации конфига для user_id={user.id}:")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail="Failed to generate VPN configuration"
            )
        
        # 6. Формируем ссылку на raw конфиг
        config_url = f"{settings.public_base_url}/api/vpn/config-raw/{telegram_id}"
        
        # 7. Форматируем expires_at для ответа
        expires_at_str = subscription.expires_at.isoformat() if subscription else None
        
        # 8. Возвращаем результат
        # Убираем /32 из адреса для ip_address (если есть)
        ip_address = peer.address.replace("/32", "") if peer.address.endswith("/32") else peer.address
        
        return schemas.VpnConfigResponse(
            config=config_text,
            ip_address=ip_address,
            expires_at=expires_at_str,
            config_url=config_url
        )
        
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        # Обрабатываем неожиданные ошибки
        print(f"[get_vpn_config] Неожиданная ошибка для telegram_id={telegram_id}:")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing VPN config request"
        )


@router.get("/config-raw/{telegram_id}")
async def get_vpn_config_raw(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """
    Возвращает чистый текст конфига VPN (WireGuard) с Content-Type: text/plain.
    Используется для прямых ссылок на конфиг.
    """
    from fastapi.responses import Response
    
    try:
        # 1. Проверяем наличие пользователя
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 2. Проверяем наличие активной подписки
        subscription = await crud.get_active_subscription(session, user.id)
        if not subscription:
            # Если подписка истекла, отзываем peer (если есть)
            peer_to_revoke = await crud.get_vpn_peer_by_user_id(session, user.id)
            if peer_to_revoke and not peer_to_revoke.is_revoked:
                try:
                    await crud.revoke_wireguard_peer(session, peer_to_revoke)
                except Exception as e:
                    print(f"[get_vpn_config_raw] Ошибка при отзыве peer для истекшей подписки: {e}")
            raise HTTPException(status_code=403, detail="Active subscription required")
        
        # 3. Получаем или создаем VPN peer
        # ВАЖНО: create_vpn_peer_for_user добавляет peer на сервер через wg set + wg-quick save
        # Peer сохраняется в БД ТОЛЬКО после успешного добавления на сервер
        # Если добавление не удалось - выбрасывается исключение, конфиг НЕ выдается
        peer = await crud.get_vpn_peer_by_user_id(session, user.id)
        if not peer:
            try:
                # Создает peer: генерирует ключи → wg set wg0 peer ... → wg-quick save wg0 → сохраняет в БД
                # Используем expires_at из подписки для expire_at пира
                peer = await crud.create_vpn_peer_for_user(session, user.id, expire_at=subscription.expires_at)
                # Коммитим peer в БД
                await session.commit()
                await session.refresh(peer)
            except ValueError as e:
                # Если у пользователя уже есть активный пир - возвращаем понятную ошибку
                raise HTTPException(
                    status_code=400,
                    detail=str(e)
                )
            except Exception as e:
                # Если не удалось добавить peer на сервер - конфиг НЕ выдаем
                print(f"[get_vpn_config_raw] Ошибка при создании VPN peer для user_id={user.id}:")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create VPN peer configuration"
                )
        
        # 4. Проверяем, что у peer есть необходимые данные
        # Если peer в БД - значит он уже успешно добавлен на сервер
        if not peer.private_key or not peer.address:
            raise HTTPException(
                status_code=500,
                detail="VPN peer configuration is incomplete"
            )
        
        # 5. Генерируем конфиг ТОЛЬКО из данных БД
        # Peer уже добавлен на сервер, можно безопасно выдавать конфиг
        try:
            config_text = _render_config(
                private_key=peer.private_key,
                address=peer.address,
                preshared_key=peer.preshared_key
            )
        except Exception as e:
            print(f"[get_vpn_config_raw] Ошибка при генерации конфига для user_id={user.id}:")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail="Failed to generate VPN configuration"
            )
        
        # 6. Возвращаем текст конфига с правильными заголовками
        return Response(
            content=config_text,
            media_type="text/plain",
            headers={
                "Content-Disposition": 'attachment; filename="vpn.conf"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[get_vpn_config_raw] Неожиданная ошибка для telegram_id={telegram_id}:")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing VPN config request"
        )
