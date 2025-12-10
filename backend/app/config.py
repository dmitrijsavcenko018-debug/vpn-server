from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Пароль синхронизирован с db в docker-compose.yml (POSTGRES_PASSWORD: vpnpass123)
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "vpn"
    db_user: str = "vpn"
    db_password: str = "vpnpass123"

    wg_host: str = "vpn.example.com"
    wg_port: int = 51820
    wg_public_key: str = "SERVER_PUBLIC_KEY_PLACEHOLDER"
    public_base_url: str = "http://localhost:8000"  # Базовый URL для публичных ссылок
    
    # SSH настройки для управления WireGuard
    ssh_host: str = "localhost"
    ssh_user: str = "root"
    ssh_key_path: str | None = None  # Путь к SSH приватному ключу
    ssh_password: str | None = None  # SSH пароль (если не используется ключ)
    wg_config_path: str = "/etc/wireguard/wg0.conf"  # Путь к конфигурации WireGuard на сервере
    
    # Telegram Bot API
    bot_token: str | None = Field(default=None, validation_alias="BOT_TOKEN")  # Токен Telegram бота для отправки уведомлений
    admin_chat_id: int | None = Field(default=None, validation_alias="BACKEND_ADMIN_CHAT_ID")  # Chat ID администратора для получения алертов

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_sync(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return f"postgresql+psycopg2://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
