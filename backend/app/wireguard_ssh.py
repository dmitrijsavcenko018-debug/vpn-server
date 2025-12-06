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
    interface: str = "wg0",
    wg_config_path: str = "/etc/wireguard/wg0.conf"
) -> bool:
    """
    Добавляет peer в WireGuard конфигурацию через SSH используя wg set.
    
    Args:
        ssh_host: SSH хост (IP или домен)
        ssh_user: SSH пользователь
        ssh_key_path: Путь к SSH приватному ключу (если используется ключ)
        ssh_password: SSH пароль (если используется пароль)
        public_key: Публичный ключ клиента
        preshared_key: Preshared ключ
        allowed_ips: IP адрес клиента (например, 10.66.66.2/32)
        interface: Имя интерфейса WireGuard (по умолчанию wg0)
        wg_config_path: Путь к конфигурации WireGuard на сервере (для сохранения)
    
    Returns:
        True если успешно, False в случае ошибки
    """
    if not public_key or not allowed_ips:
        logger.error("[add_peer_to_wg0] Отсутствуют обязательные параметры: public_key или allowed_ips")
        return False
    
    # Формируем команду wg set для добавления peer
    # wg set wg0 peer <public_key> allowed-ips <allowed_ips>/32 [preshared-key <psk>]
    if preshared_key:
        # Если есть preshared_key, передаем его через stdin
        # Используем printf для более надежной передачи (echo может интерпретировать специальные символы)
        wg_set_cmd = f"printf '%s' '{preshared_key}' | sudo wg set {interface} peer {public_key} allowed-ips {allowed_ips} preshared-key /dev/stdin"
    else:
        wg_set_cmd = f"sudo wg set {interface} peer {public_key} allowed-ips {allowed_ips}"
    
    # Сохраняем конфигурацию на диск, чтобы после перезагрузки не пропало
    # wg-quick save wg0 сохраняет текущую конфигурацию в файл
    save_cmd = f"sudo wg-quick save {interface}"
    
    # Объединяем команды
    full_cmd = f"{wg_set_cmd} && {save_cmd}"
    
    # Формируем SSH команду
    if ssh_key_path:
        ssh_cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            full_cmd
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
            full_cmd
        ]
    else:
        logger.error("[add_peer_to_wg0] Не указан ни ssh_key_path, ни ssh_password")
        return False
    
    try:
        logger.info(f"[add_peer_to_wg0] Добавляю peer {public_key[:20]}... на {ssh_host} через wg set")
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
    interface: str = "wg0",
    wg_config_path: str = "/etc/wireguard/wg0.conf"
) -> bool:
    """
    Удаляет peer из WireGuard конфигурации через SSH используя wg set.
    
    Args:
        ssh_host: SSH хост
        ssh_user: SSH пользователь
        ssh_key_path: Путь к SSH приватному ключу
        ssh_password: SSH пароль
        public_key: Публичный ключ клиента для удаления
        interface: Имя интерфейса WireGuard (по умолчанию wg0)
        wg_config_path: Путь к конфигурации WireGuard (для сохранения)
    
    Returns:
        True если успешно, False в случае ошибки
    """
    if not public_key:
        logger.error("[remove_peer_from_wg0] Отсутствует public_key")
        return False
    
    # Команда для удаления peer через wg set
    # wg set wg0 peer <public_key> remove
    remove_peer_cmd = f"sudo wg set {interface} peer {public_key} remove"
    
    # Сохраняем конфигурацию на диск
    save_cmd = f"sudo wg-quick save {interface}"
    
    # Объединяем команды
    full_cmd = f"{remove_peer_cmd} && {save_cmd}"
    
    # Формируем SSH команду
    if ssh_key_path:
        ssh_cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            full_cmd
        ]
    elif ssh_password:
        ssh_cmd = [
            "sshpass", "-p", ssh_password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ssh_host}",
            full_cmd
        ]
    else:
        logger.error("[remove_peer_from_wg0] Не указан ни ssh_key_path, ни ssh_password")
        return False
    
    try:
        logger.info(f"[remove_peer_from_wg0] Удаляю peer {public_key[:20]}... с {ssh_host} через wg set")
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

