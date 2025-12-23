from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        import logging
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logging.error(f"[ApiClient] Ошибка подключения к {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logging.error(f"[ApiClient] HTTP ошибка {e.response.status_code} для {url}: {e.response.text}")
            raise
        except Exception as e:
            logging.error(f"[ApiClient] Неожиданная ошибка при запросе {url}: {e}")
            raise

    async def ensure_user(self, telegram_id: int) -> Any:
        return await self._request("POST", "/api/users/by-telegram", json={"telegram_id": telegram_id})

    async def get_or_create_user(self, telegram_id: int) -> Any:
        """Алиас для ensure_user для совместимости"""
        return await self.ensure_user(telegram_id)

    async def get_subscription(self, telegram_id: int) -> Any:
        return await self._request("GET", f"/api/subscriptions/{telegram_id}")

    async def create_month_subscription(self, telegram_id: int) -> Any:
        return await self._request("POST", f"/api/subscriptions/{telegram_id}/create-month")

    async def activate_subscription(self, telegram_id: int, months: int) -> Any:
        """
        Активирует или продлевает подписку на указанное количество месяцев.
        
        Backend должен предоставить endpoint:
        POST /api/subscriptions/{telegram_id}/activate
        Body: {"months": int}
        
        Если такого endpoint нет, backend-разработчик должен его создать.
        Логика должна быть аналогична create_or_extend_month_subscription,
        но с возможностью указать количество месяцев.
        """
        return await self._request(
            "POST",
            f"/api/subscriptions/{telegram_id}/activate",
            json={"months": months}
        )

    async def activate_test_subscription(self, telegram_id: int) -> Any:
        """
        Активирует тестовый тариф на 24 часа.
        
        Backend должен предоставить endpoint:
        POST /api/subscriptions/{telegram_id}/activate-test
        """
        return await self._request(
            "POST",
            f"/api/subscriptions/{telegram_id}/activate-test"
        )

    async def get_vpn_config(self, telegram_id: int) -> Any:
        return await self._request("GET", f"/api/vpn/config/{telegram_id}")

    async def get_admin_stats(self) -> Any:
        """Получить статистику для админ-панели"""
        return await self._request("GET", "/api/admin/stats")

    async def get_admin_expiring(self) -> Any:
        """Получить список подписок, истекающих в ближайшие 24 часа"""
        return await self._request("GET", "/api/admin/expiring")

    async def get_admin_revoked(self) -> Any:
        """Получить список отключенных peer за последние 24 часа"""
        return await self._request("GET", "/api/admin/revoked")

    async def get_admin_user_info(self, telegram_id: int) -> Any:
        """Получить информацию о пользователе по telegram_id"""
        return await self._request("GET", f"/api/admin/user/{telegram_id}")






    async def admin_disable_user(self, telegram_id: int) -> dict:
        """Отключить VPN для пользователя (отозвать активный peer)"""
        return await self._request("POST", f"/api/admin/user/{telegram_id}/disable")

    async def admin_enable_user(self, telegram_id: int) -> dict:
        """Включить VPN для пользователя (создать новый peer)"""
        return await self._request("POST", f"/api/admin/user/{telegram_id}/enable")

    async def admin_users(self, limit: int = 15, offset: int = 0) -> dict:
        """Получить список пользователей для админ-панели"""
        return await self._request("GET", f"/api/admin/users?limit={limit}&offset={offset}")
