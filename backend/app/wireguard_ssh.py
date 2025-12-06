"""
Модуль для управления WireGuard конфигурацией через SSH
"""
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def add_peer_to_wg0(
    ssh_host: str,
    ssh_user: str,
    ssh_key_path: Optional[str] = None,
    ssh_password: Optional[str] = None,
    public_key: str = "",
    preshared_key: str = "",
    allowed_ips: str = "",
    wg_config_path: str = "/etc/wireguard/wg0.conf"
) -> bool:
    """
    Добавляет peer в WireGuard конфигурацию через SSH.
    
    Args:
        ssh_host: SSH хост (IP или домен)
        ssh_user: SSH пользователь
        ssh_key_path: Путь к SSH приватному ключу (если используется ключ)
        ssh_password: SSH пароль (если используется пароль)
        public_key: Публичный ключ клиента
        preshared_key: Preshared ключ
        allowed_ips: IP адрес клиента (например, 10.66.66.2/32)
        wg_config_path: Путь к конфигурации WireGuard на сервере
    
    Returns:
        True если успешно, False в случае ошибки
    """
    if not public_key or not allowed_ips:
        logger.error("[add_peer_to_wg0] Отсутствуют обязательные параметры: public_key или allowed_ips")
        return False
    
    # Формируем секцию peer для добавления
    peer_section = f"\n[Peer]\nPublicKey = {public_key}\n"
    if preshared_key:
        peer_section += f"PresharedKey = {preshared_key}\n"
    peer_section += f"AllowedIPs = {allowed_ips}\n"
    
    # Формируем команду для добавления peer в конфиг
    # Используем echo для добавления в конец файла
    add_peer_cmd = f"echo '{peer_section}' | sudo tee -a {wg_config_path} > /dev/null"
    
    # Команда для синхронизации конфигурации WireGuard без перезапуска
    # Используем временный файл, так как process substitution может не работать через SSH
    sync_cmd = "sudo bash -c 'wg-quick strip wg0 > /tmp/wg0_stripped.conf && wg syncconf wg0 /tmp/wg0_stripped.conf && rm -f /tmp/wg0_stripped.conf'"
    
    # Формируем SSH команду
    if ssh_key_path:
        ssh_cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            f"{add_peer_cmd} && {sync_cmd}"
        ]
    elif ssh_password:
        # Используем sshpass для пароля
        ssh_cmd = [
            "sshpass", "-p", ssh_password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            f"{add_peer_cmd} && {sync_cmd}"
        ]
    else:
        logger.error("[add_peer_to_wg0] Не указан ни ssh_key_path, ни ssh_password")
        return False
    
    try:
        logger.info(f"[add_peer_to_wg0] Добавляю peer {public_key[:20]}... на {ssh_host}")
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        logger.info(f"[add_peer_to_wg0] Peer успешно добавлен: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[add_peer_to_wg0] Ошибка SSH команды: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("[add_peer_to_wg0] Таймаут SSH соединения")
        return False
    except FileNotFoundError:
        logger.error("[add_peer_to_wg0] SSH клиент не найден. Установите openssh-client")
        return False
    except Exception as e:
        logger.error(f"[add_peer_to_wg0] Неожиданная ошибка: {e}")
        return False


def remove_peer_from_wg0(
    ssh_host: str,
    ssh_user: str,
    ssh_key_path: Optional[str] = None,
    ssh_password: Optional[str] = None,
    public_key: str = "",
    wg_config_path: str = "/etc/wireguard/wg0.conf"
) -> bool:
    """
    Удаляет peer из WireGuard конфигурации через SSH.
    
    Args:
        ssh_host: SSH хост
        ssh_user: SSH пользователь
        ssh_key_path: Путь к SSH приватному ключу
        ssh_password: SSH пароль
        public_key: Публичный ключ клиента для удаления
        wg_config_path: Путь к конфигурации WireGuard
    
    Returns:
        True если успешно, False в случае ошибки
    """
    if not public_key:
        logger.error("[remove_peer_from_wg0] Отсутствует public_key")
        return False
    
    # Команда для удаления peer по PublicKey
    # Используем sed для удаления секции [Peer] с указанным PublicKey
    # Экранируем специальные символы в public_key для sed
    escaped_public_key = public_key.replace("/", "\\/").replace(".", "\\.")
    remove_peer_cmd = (
        f"sudo sed -i '/^\\[Peer\\]$/,/^$/ {{ "
        f"/PublicKey = {escaped_public_key}/,"
        f"/^$/d; }}' {wg_config_path}"
    )
    
    # Команда для синхронизации конфигурации
    # Используем временный файл, так как process substitution может не работать через SSH
    sync_cmd = "sudo bash -c 'wg-quick strip wg0 > /tmp/wg0_stripped.conf && wg syncconf wg0 /tmp/wg0_stripped.conf && rm -f /tmp/wg0_stripped.conf'"
    
    # Формируем SSH команду
    if ssh_key_path:
        ssh_cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            f"{remove_peer_cmd} && {sync_cmd}"
        ]
    elif ssh_password:
        ssh_cmd = [
            "sshpass", "-p", ssh_password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            f"{remove_peer_cmd} && {sync_cmd}"
        ]
    else:
        logger.error("[remove_peer_from_wg0] Не указан ни ssh_key_path, ни ssh_password")
        return False
    
    try:
        logger.info(f"[remove_peer_from_wg0] Удаляю peer {public_key[:20]}... с {ssh_host}")
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        logger.info(f"[remove_peer_from_wg0] Peer успешно удален: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[remove_peer_from_wg0] Ошибка SSH команды: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("[remove_peer_from_wg0] Таймаут SSH соединения")
        return False
    except FileNotFoundError:
        logger.error("[remove_peer_from_wg0] SSH клиент не найден. Установите openssh-client")
        return False
    except Exception as e:
        logger.error(f"[remove_peer_from_wg0] Неожиданная ошибка: {e}")
        return False

