"""Módulo de utilitários compartilhados"""
import os
import sys
import stat
import json
import ctypes
import winreg
import datetime
import tempfile
from pathlib import Path
from typing import Optional

try:
    from config import SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE
except ImportError:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    if isinstance(SECRET_KEY, str):
        SECRET_KEY = SECRET_KEY.encode()
    API_URL = os.getenv('API_URL', '')
    API_URL_SITE = os.getenv('API_URL_SITE', '')
    AUTH_CODE = os.getenv('AUTH_CODE', '')


def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto para recursos, funciona em dev e PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_safe_download_dir() -> Path:
    """Retorna diretório temporário seguro do sistema"""
    try:
        temp_base = Path(tempfile.gettempdir()) / "GameStore_Temp"
        temp_base.mkdir(parents=True, exist_ok=True)
        test_file = temp_base / ".test"
        test_file.touch()
        test_file.unlink()
        return temp_base
    except Exception:
        script_dir = Path(__file__).parent / "temp_downloads"
        script_dir.mkdir(parents=True, exist_ok=True)
        return script_dir


def get_log_directory() -> Path:
    """Retorna o diretório de logs no AppData"""
    try:
        if sys.platform == "win32":
            appdata = Path.home() / "AppData/Roaming"
        elif sys.platform == "linux":
            appdata = Path.home() / ".local/share"
        elif sys.platform == "darwin":
            appdata = Path.home() / "Library/Application Support"
        else:
            appdata = Path.home()
        log_dir = appdata / "GamesStoreLauncher" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    except Exception:
        temp_dir = Path(tempfile.gettempdir()) / "GamesStoreLauncher" / "logs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir


def log_message(message: str, include_traceback: bool = False) -> None:
    """Registra mensagens no arquivo de log (compatível com .exe) - ESCREVE SINCRONAMENTE"""
    try:
        if getattr(sys, 'frozen', False):
            log_dir = Path(os.getenv('APPDATA')) / "GamesStoreLauncher" / "logs"
        else:
            log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'log.txt'
        
        # Abrir em modo 'a' e forçar flush para garantir escrita imediata
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
            
            if include_traceback:
                import traceback
                tb = traceback.format_exc()
                f.write(f"[{timestamp}] TRACEBACK:\n{tb}\n")
            
            # FORÇAR flush para garantir que o log seja escrito imediatamente
            f.flush()
            # No Windows, também forçar sincronização
            if hasattr(os, 'fsync'):
                try:
                    os.fsync(f.fileno())
                except:
                    pass
        
        # Também imprimir no console para debug
        print(f"[LOG] {message}")
    except Exception as e:
        print(f"[LOG ERROR] Falha ao escrever log: {e}")
        print(f"[LOG] {message}")


def get_steam_directory() -> Optional[str]:
    """Obtém o diretório de instalação do Steam do registro do Windows"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            return steam_path.replace("/", "\\")
    except Exception:
        return None


def get_disk_serial() -> str:
    """Obtém o número de série do disco rígido"""
    try:
        volume_name_buffer = ctypes.create_unicode_buffer(1024)
        file_system_name_buffer = ctypes.create_unicode_buffer(1024)
        serial_number = ctypes.c_ulong()
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"),
            volume_name_buffer,
            ctypes.sizeof(volume_name_buffer),
            ctypes.byref(serial_number),
            None,
            None,
            file_system_name_buffer,
            ctypes.sizeof(file_system_name_buffer),
        )
        return str(serial_number.value)
    except Exception:
        return "UNKNOWN_DISK"


def get_mac_address() -> str:
    """Obtém o endereço MAC da primeira interface de rede ativa"""
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if getattr(psutil, "AF_LINK", 17) == addr.family:
                    mac = addr.address.replace(":", "")
                    if mac and mac != "000000000000":
                        return mac
        return "UNKNOWN_MAC"
    except Exception:
        return "UNKNOWN_MAC"


def generate_hwid() -> str:
    """Gera HWID único baseado em disco e MAC"""
    import hashlib
    disk_id = get_disk_serial()
    mac_id = get_mac_address()
    raw = f"{disk_id}_{mac_id}"
    return hashlib.sha256(raw.encode()).hexdigest().upper()[:24]


def remove_readonly(func, path, excinfo):
    """Helper para remover arquivos read-only"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

