"""
Модуль для управления WireGuard конфигурацией через SSH или локально
"""
import logging
import subprocess
import os
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
    Добавляет peer в WireGuard конфигурацию через SSH или локально.
    Если доступен /etc/wireguard и ssh_host == "localhost" - выполняет команды локально.
    Иначе - через SSH.
    
    Args:
        ssh_host: SSH хост (IP или домен, или "localhost" для локального выполнения)
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
    
    # Проверяем, можем ли выполнить команды локально (если backend в контейнере с доступом к /etc/wireguard)
    use_local = (ssh_host == "localhost" or ssh_host == "127.0.0.1") and os.path.exists("/etc/wireguard")
    
    # Формируем команду wg set для добавления peer
    # wg set wg0 peer <public_key> allowed-ips <allowed_ips>/32 [preshared-key <psk>]
    if preshared_key:
        # Если есть preshared_key, передаем его через stdin
        # Используем printf для более надежной передачи
        if use_local:
            # Локальное выполнение: используем subprocess с stdin
            try:
                logger.info(f"[add_peer_to_wg0] Добавляю peer {public_key[:20]}... локально через wg set")
                # Выполняем wg set с preshared_key через stdin
                wg_set_process = subprocess.Popen(
                    ["sudo", "wg", "set", interface, "peer", public_key, "allowed-ips", allowed_ips, "preshared-key", "/dev/stdin"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = wg_set_process.communicate(input=preshared_key, timeout=10)
                if wg_set_process.returncode != 0:
                    logger.error(f"[add_peer_to_wg0] Ошибка wg set: {stderr}")
                    return False
                
                # Сохраняем конфигурацию
                save_result = subprocess.run(
                    ["sudo", "wg-quick", "save", interface],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True
                )
                logger.info(f"[add_peer_to_wg0] Peer успешно добавлен локально")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"[add_peer_to_wg0] Ошибка локальной команды: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"[add_peer_to_wg0] Неожиданная ошибка при локальном выполнении: {e}")
                return False
        else:
            # SSH выполнение
            wg_set_cmd = f"printf '%s' '{preshared_key}' | sudo wg set {interface} peer {public_key} allowed-ips {allowed_ips} preshared-key /dev/stdin"
    else:
        if use_local:
            # Локальное выполнение без preshared_key
            try:
                logger.info(f"[add_peer_to_wg0] Добавляю peer {public_key[:20]}... локально через wg set")
                # Выполняем wg set
                wg_set_result = subprocess.run(
                    ["sudo", "wg", "set", interface, "peer", public_key, "allowed-ips", allowed_ips],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True
                )
                
                # Сохраняем конфигурацию
                save_result = subprocess.run(
                    ["sudo", "wg-quick", "save", interface],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True
                )
                logger.info(f"[add_peer_to_wg0] Peer успешно добавлен локально")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"[add_peer_to_wg0] Ошибка локальной команды: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"[add_peer_to_wg0] Неожиданная ошибка при локальном выполнении: {e}")
                return False
        else:
            # SSH выполнение
            wg_set_cmd = f"sudo wg set {interface} peer {public_key} allowed-ips {allowed_ips}"
    
    # Если не локальное выполнение - используем SSH
    if not use_local:
        # Сохраняем конфигурацию на диск, чтобы после перезагрузки не пропало
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
            logger.error("[add_peer_to_wg0] Не указан ни ssh_key_path, ни ssh_password для SSH подключения")
            return False
        
        try:
            logger.info(f"[add_peer_to_wg0] Добавляю peer {public_key[:20]}... на {ssh_host} через SSH")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            logger.info(f"[add_peer_to_wg0] Peer успешно добавлен через SSH: {result.stdout}")
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
    Удаляет peer из WireGuard конфигурации через SSH или локально.
    Если доступен /etc/wireguard и ssh_host == "localhost" - выполняет команды локально.
    Иначе - через SSH.
    
    Args:
        ssh_host: SSH хост (IP или домен, или "localhost" для локального выполнения)
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
    
    # Проверяем, можем ли выполнить команды локально
    use_local = (ssh_host == "localhost" or ssh_host == "127.0.0.1") and os.path.exists("/etc/wireguard")
    
    if use_local:
        # Локальное выполнение
        try:
            logger.info(f"[remove_peer_from_wg0] Удаляю peer {public_key[:20]}... локально через wg set")
            # Удаляем peer
            remove_result = subprocess.run(
                ["sudo", "wg", "set", interface, "peer", public_key, "remove"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            
            # Сохраняем конфигурацию
            save_result = subprocess.run(
                ["sudo", "wg-quick", "save", interface],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            logger.info(f"[remove_peer_from_wg0] Peer успешно удален локально")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[remove_peer_from_wg0] Ошибка локальной команды: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"[remove_peer_from_wg0] Неожиданная ошибка при локальном выполнении: {e}")
            return False
    else:
        # SSH выполнение
        # Команда для удаления peer через wg set
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
            logger.error("[remove_peer_from_wg0] Не указан ни ssh_key_path, ни ssh_password для SSH подключения")
            return False
        
        try:
            logger.info(f"[remove_peer_from_wg0] Удаляю peer {public_key[:20]}... с {ssh_host} через SSH")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            logger.info(f"[remove_peer_from_wg0] Peer успешно удален через SSH: {result.stdout}")
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

