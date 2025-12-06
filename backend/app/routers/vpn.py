import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..config import settings
from ..deps import get_session

router = APIRouter(prefix="/api/vpn", tags=["vpn"])


def _render_config(private_key: str, address: str) -> str:
    """
    Генерирует WireGuard конфиг для клиента.
    Включает AllowedIPs и PersistentKeepalive для корректной работы VPN.
    """
    # Убеждаемся, что address содержит /32
    if not address.endswith("/32"):
        if "/" in address:
            # Если есть другой префикс, заменяем на /32
            address = address.split("/")[0] + "/32"
        else:
            # Если нет префикса, добавляем /32
            address = address + "/32"
    
    return (
        "[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {address}\n"
        "DNS = 1.1.1.1\n\n"
        "[Peer]\n"
        f"PublicKey = {settings.wg_public_key}\n"
        f"Endpoint = {settings.wg_host}:{settings.wg_port}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        "PersistentKeepalive = 25\n"
    )


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
            raise HTTPException(status_code=403, detail="Active subscription required")
        
        # 3. Получаем или создаем VPN peer
        peer = await crud.get_vpn_peer_by_user_id(session, user.id)
        if not peer:
            try:
                peer = await crud.create_vpn_peer_for_user(session, user.id)
            except Exception as e:
                # Логируем ошибку создания peer
                print(f"[get_vpn_config] Ошибка при создании VPN peer для user_id={user.id}:")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create VPN peer configuration"
                )
        
        # 4. Проверяем, что у peer есть необходимые данные
        if not peer.private_key or not peer.address:
            raise HTTPException(
                status_code=500,
                detail="VPN peer configuration is incomplete"
            )
        
        # 5. Генерируем конфиг
        try:
            config_text = _render_config(peer.private_key, peer.address)
        except Exception as e:
            print(f"[get_vpn_config] Ошибка при генерации конфига для user_id={user.id}:")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail="Failed to generate VPN configuration"
            )
        
        # 6. Формируем ссылку на raw конфиг
        config_url = f"{settings.public_base_url}/api/vpn/config-raw/{telegram_id}"
        
        # 7. Возвращаем результат
        return schemas.VpnConfigResponse(
            user_id=user.id,
            peer_id=peer.id,
            address=peer.address,
            config=config_text,
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
            raise HTTPException(status_code=403, detail="Active subscription required")
        
        # 3. Получаем или создаем VPN peer
        peer = await crud.get_vpn_peer_by_user_id(session, user.id)
        if not peer:
            try:
                peer = await crud.create_vpn_peer_for_user(session, user.id)
            except Exception as e:
                print(f"[get_vpn_config_raw] Ошибка при создании VPN peer для user_id={user.id}:")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create VPN peer configuration"
                )
        
        # 4. Проверяем, что у peer есть необходимые данные
        if not peer.private_key or not peer.address:
            raise HTTPException(
                status_code=500,
                detail="VPN peer configuration is incomplete"
            )
        
        # 5. Генерируем конфиг
        try:
            config_text = _render_config(peer.private_key, peer.address)
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
