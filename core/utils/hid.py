"""
Utilitários para HID DLL
"""
import os
import sys
import shutil

from utils import get_steam_directory, log_message


def ensure_hid_dll():
    """Garante que hid.dll esteja na pasta da Steam"""
    try:
        steam_path = get_steam_directory()
        if not steam_path:
            log_message("[HID] Steam não encontrada")
            return

        # Localizar hid.dll na pasta config do app
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            # Subir dois níveis para chegar à raiz do projeto (core/utils -> projeto)
            base_path = os.path.dirname(os.path.dirname(base_path))
            
        source_dll = os.path.join(base_path, "config", "hid.dll")
        if not os.path.exists(source_dll):
            # Tentar na pasta assets/config como fallback
            source_dll = os.path.join(base_path, "assets", "config", "hid.dll")
            
        if not os.path.exists(source_dll):
            log_message(f"[HID] DLL original não encontrada em: {source_dll}")
            return

        dest_dll = os.path.join(steam_path, "hid.dll")
        
        # Copiar se não existir ou se for diferente
        should_copy = True
        if os.path.exists(dest_dll):
            try:
                src_stat = os.stat(source_dll)
                dst_stat = os.stat(dest_dll)
                if src_stat.st_size == dst_stat.st_size:
                    should_copy = False
            except:
                pass
        
        if should_copy:
            try:
                shutil.copy2(source_dll, dest_dll)
                log_message(f"[HID] hid.dll copiada para: {dest_dll}")
            except Exception as e:
                log_message(f"[HID] Erro ao copiar hid.dll: {e}")
        else:
            log_message("[HID] hid.dll já existe e parece atualizada")
            
    except Exception as e:
        log_message(f"[HID] Erro geral: {e}")
