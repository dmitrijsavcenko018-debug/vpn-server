import os
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Пароль синхронизирован с db в docker-compose.yml (POSTGRES_PASSWORD: vpnpass123)
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "vpn"
    db_user: str = "vpn"
    db_password: str = "vpnpass123"

    wg_host: str = Field(default="vpn.example.com", validation_alias="WG_HOST")
    wg_port: int = Field(default=51820, validation_alias="WG_PORT")
    wg_public_key: str = "SERVER_PUBLIC_KEY_PLACEHOLDER"
    
    @field_validator("wg_public_key", mode="after")
    @classmethod
    def auto_load_wg_public_key(cls, v: str) -> str:
        """
        Автоматически загружает публичный ключ сервера из файла,
        если переменная окружения не задана или содержит placeholder.
        """
        # Если ключ уже задан и не является placeholder - используем его
        if v and v != "SERVER_PUBLIC_KEY_PLACEHOLDER" and len(v) > 20:
            return v
        
        # Пробуем прочитать из файла
        server_key_path = "/etc/wireguard/server_public.key"
        if os.path.exists(server_key_path):
            try:
                with open(server_key_path, "r") as f:
                    key = f.read().strip()
                    if key and len(key) > 20:
                        return key
            except Exception:
                pass
        
        # Если не удалось загрузить - возвращаем исходное значение
        return v
    public_base_url: str = "http://localhost:8000"  # Базовый URL для публичных ссылок
    
    # SSH настройки для управления WireGuard
    # Режим управления WireGuard:
    # - "ssh": все команды wg/wg-quick выполняются на хосте по SSH
    # - "local": (на будущее) локальное выполнение в окружении процесса
    wg_mode: str = Field(default="ssh", validation_alias="WG_MODE")
    wg_interface: str = Field(default="wg0", validation_alias="WG_INTERFACE")

    # SSH параметры для WG_MODE=ssh
    # (намеренно отдельные переменные, чтобы исключить путаницу с "localhost" внутри контейнера)
    wg_ssh_host: str = Field(default="host.docker.internal", validation_alias="WG_SSH_HOST")
    wg_ssh_port: int = Field(default=22, validation_alias="WG_SSH_PORT")
    wg_ssh_user: str = Field(default="root", validation_alias="WG_SSH_USER")
    wg_ssh_key_path: str | None = Field(default=None, validation_alias="WG_SSH_KEY_PATH")

    # Старые переменные (совместимость): если где-то еще используется
    ssh_host: str = Field(default="localhost", validation_alias="SSH_HOST")
    ssh_user: str = Field(default="root", validation_alias="SSH_USER")
    ssh_key_path: str | None = Field(default=None, validation_alias="SSH_KEY_PATH")  # Путь к SSH приватному ключу
    ssh_password: str | None = Field(default=None, validation_alias="SSH_PASSWORD")  # SSH пароль (если не используется ключ)

    wg_config_path: str = "/etc/wireguard/wg0.conf"  # Путь к конфигурации WireGuard на хосте (для wg-quick save)
    
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
