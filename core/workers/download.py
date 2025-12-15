"""
Workers de download - DownloadWorker, DownloadWorkerSignals, DownloadThread
"""
import os
import re
import sys
import json
import stat
import time
import shutil
import zipfile
import tempfile
import datetime
import subprocess
from pathlib import Path

import requests

from PyQt5.QtCore import QObject, QRunnable, QThread, pyqtSignal, pyqtSlot as Slot

from utils import get_safe_download_dir, log_message, API_URL, AUTH_CODE
from core.utils.winrar import find_winrar, ensure_winrar_installed


class DownloadWorkerSignals(QObject):
    """Sinais para comunicação do worker de download"""
    progress = pyqtSignal(int)  # Porcentagem (0-100)
    speed = pyqtSignal(float)   # Velocidade em MB/s
    downloaded = pyqtSignal(int, int)  # (baixado_MB, total_MB)
    status = pyqtSignal(str)  # Texto de status
    success = pyqtSignal(str, str, str)  # (message, filepath, game_id)
    error = pyqtSignal(str)
    # Removido finished signal - não é necessário e pode causar problemas


class DownloadWorker(QRunnable):
    """Worker responsável pelo download, extração e instalação"""
    
    def __init__(self, game_id, download_url=None, game_name=None, steam_path=None):
        super().__init__()
        self.game_id = game_id
        self.download_url = download_url
        self.game_name = game_name
        self.steam_path = steam_path
        self.signals = DownloadWorkerSignals()
        self._last_progress = 0
    
    def get_game_name_from_steam(self, appid):
        """Busca o nome do jogo na Steam API"""
        try:
            steam_api_url = f"http://store.steampowered.com/api/appdetails?appids={appid}"
            response = requests.get(steam_api_url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            if str(appid) in data and data[str(appid)].get('success'):
                game_name = data[str(appid)]['data'].get('name', 'jogo')
                return game_name
            else:
                return f'jogo_{appid}'
                
        except Exception as e:
            return f'jogo_{appid}'
    
    @Slot()
    def run(self):
        """Executa download, extração e instalação"""
        log_message(f"[DOWNLOAD WORKER] Worker iniciado - game_id={self.game_id}, game_name={self.game_name}")
        filepath = None
        temp_dir = None
        
        try:
            # FASE 1: DOWNLOAD
            log_message(f"[DOWNLOAD WORKER] FASE 1: Preparando download para {self.game_id}")
            self.signals.status.emit("Preparando download...")
            
            if not self.game_name:
                log_message(f"[DOWNLOAD WORKER] Nome não fornecido, buscando na Steam API...")
                self.game_name = self.get_game_name_from_steam(self.game_id)
                log_message(f"[DOWNLOAD WORKER] Nome obtido: {self.game_name}")
            
            if not self.download_url:
                if not API_URL or not AUTH_CODE:
                    raise Exception("Configuração de API não encontrada")
                
                self.download_url = f"{API_URL}?appid={self.game_id}&auth_code={AUTH_CODE}"
                log_message(f"[DOWNLOAD WORKER] URL de download gerada")
            
            log_message(f"[DOWNLOAD WORKER] Iniciando download: {self.game_name} (ID: {self.game_id})")
            self.signals.status.emit(f"Baixando {self.game_name}...")
            
            headers = {
                'Connection': 'keep-alive',
                'Accept-Encoding': 'gzip, deflate',
                'User-Agent': 'Mozilla/5.0'
            }
            
            response = requests.get(
                self.download_url, 
                headers=headers, 
                stream=True, 
                allow_redirects=True, 
                timeout=30
            )
            response.raise_for_status()
            
            # Detectar extensão
            content_type = response.headers.get('content-type', '').lower()
            content_disposition = response.headers.get('content-disposition', '').lower()
            
            if 'zip' in content_type or 'zip' in content_disposition:
                extension = '.zip'
            elif 'rar' in content_type or 'rar' in content_disposition:
                extension = '.rar'
            else:
                total_size = int(response.headers.get('content-length', 0))
                extension = '.rar' if total_size > 100 * 1024 * 1024 else '.zip'
            
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', self.game_name)
            download_dir = get_safe_download_dir()
            filename = f"{safe_name} ({self.game_id}){extension}"
            filepath = download_dir / filename
            
            if filepath.exists():
                try:
                    filepath.unlink()
                except PermissionError:
                    timestamp = int(time.time())
                    filename = f"{safe_name} ({self.game_id})_{timestamp}{extension}"
                    filepath = download_dir / filename
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            CHUNK_SIZE = 1024 * 1024  # 1MB
            
            start_time = time.time()
            last_update_time = start_time
            last_downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        elapsed_since_last = current_time - last_update_time
                        
                        if elapsed_since_last >= 0.5:
                            bytes_since_last = downloaded - last_downloaded
                            speed_mbps = (bytes_since_last / (1024 * 1024)) / elapsed_since_last
                            
                            self.signals.speed.emit(speed_mbps)
                            
                            last_update_time = current_time
                            last_downloaded = downloaded
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            
                            if progress != self._last_progress:
                                self.signals.progress.emit(progress)
                                self._last_progress = progress
                            
                            downloaded_mb = int(downloaded / (1024 * 1024))
                            total_mb = int(total_size / (1024 * 1024))
                            self.signals.downloaded.emit(downloaded_mb, total_mb)
            
            elapsed = time.time() - start_time
            avg_speed_mbps = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            
            self.signals.progress.emit(100)
            
            # FASE 2: EXTRAÇÃO E INSTALAÇÃO
            if self.steam_path:
                self.signals.status.emit("Extraindo arquivos...")
                self.signals.progress.emit(0)
                
                temp_base = Path(tempfile.gettempdir()) / "GameStore_Extract"
                temp_base.mkdir(parents=True, exist_ok=True)
                temp_dir = temp_base / f"extract_{int(time.time())}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                # Extrair
                if str(filepath).lower().endswith('.zip'):
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        total_files = len(zip_ref.namelist())
                        for i, file in enumerate(zip_ref.namelist()):
                            zip_ref.extract(file, temp_dir)
                            progress = int((i / total_files) * 100)
                            self.signals.progress.emit(progress)
                    log_message("[DOWNLOAD WORKER] Extração ZIP concluída")
                
                elif str(filepath).lower().endswith('.rar'):
                    # Tentar usar unrar via Python puro primeiro
                    try:
                        import rarfile
                        with rarfile.RarFile(filepath) as rf:
                            total_files = len(rf.namelist())
                            for i, member in enumerate(rf.namelist()):
                                rf.extract(member, temp_dir)
                                progress = int((i / total_files) * 100)
                                self.signals.progress.emit(progress)
                        log_message("[DOWNLOAD WORKER] Extração RAR concluída (rarfile)")
                    except ImportError:
                        # Fallback: usar WinRAR de forma mais segura
                        winrar_path = find_winrar()
                        
                        # Se não encontrar, tentar instalar automaticamente
                        if not winrar_path:
                            log_message("[DOWNLOAD WORKER] WinRAR não encontrado. Tentando instalar automaticamente...")
                            self.signals.status.emit("Instalando WinRAR...")
                            winrar_path = ensure_winrar_installed(self.signals)
                        
                        if not winrar_path:
                            raise Exception("WinRAR não encontrado e não foi possível instalar automaticamente")
                        
                        # Usar Popen com flags adequadas para .exe
                        is_frozen = getattr(sys, 'frozen', False)
                        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if is_frozen and sys.platform == 'win32' else 0
                        
                        # Executar de forma mais segura
                        proc = subprocess.Popen(
                            [winrar_path, 'x', '-ibck', '-inul', str(filepath), str(temp_dir)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            creationflags=creation_flags if creation_flags else 0
                        )
                        proc.wait(timeout=300)
                        log_message("[DOWNLOAD WORKER] Extração RAR concluída (WinRAR)")
                
                self.signals.progress.emit(100)
                self.signals.status.emit("Instalando arquivos do jogo...")
                self.signals.progress.emit(0)
                
                log_message("[DOWNLOAD WORKER] Processando arquivos do jogo...")
                extracted_game_id, extracted_game_name, moved_files = self.process_game_files(
                    str(temp_dir), 
                    self.steam_path
                )
                log_message(f"[DOWNLOAD WORKER] Arquivos processados - {extracted_game_name} (ID: {extracted_game_id})")
                
                log_message(f"[DOWNLOAD WORKER] Registrando jogo: {extracted_game_name} (ID: {extracted_game_id})")
                self.register_game(extracted_game_name, extracted_game_id, moved_files)
                log_message("[DOWNLOAD WORKER] Jogo registrado com sucesso")
                
                log_message("[DOWNLOAD WORKER] Enviando progress 100%")
                self.signals.progress.emit(100)
                log_message("[DOWNLOAD WORKER] Progress 100% enviado")
                
                log_message(f"[DOWNLOAD WORKER] Instalação concluída - {extracted_game_name} (ID: {extracted_game_id})")
                try:
                    self.signals.success.emit(
                        f"{extracted_game_name} instalado com sucesso!\n"
                        f"Velocidade média: {avg_speed_mbps:.2f} MB/s\n"
                        f"Reinicie a Steam para ver o jogo.",
                        str(filepath),
                        extracted_game_id
                    )
                    log_message("[DOWNLOAD WORKER] Signal success.emit enviado para instalação COM SUCESSO")
                except Exception as e:
                    log_message(f"[DOWNLOAD WORKER] ERRO ao emitir success para instalação: {e}", include_traceback=True)
            else:
                log_message(f"[DOWNLOAD WORKER] Download concluído sem instalação - {self.game_name} (ID: {self.game_id})")
                try:
                    self.signals.success.emit(
                        f"Download de '{self.game_name}' concluído!\n"
                        f"Velocidade média: {avg_speed_mbps:.2f} MB/s",
                        str(filepath),
                        self.game_id
                    )
                    log_message("[DOWNLOAD WORKER] Signal success.emit enviado para download simples COM SUCESSO")
                except Exception as e:
                    log_message(f"[DOWNLOAD WORKER] ERRO ao emitir success para download: {e}", include_traceback=True)
            
        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            log_message(f"[DOWNLOAD WORKER] ERRO durante download/instalacao: {error_msg}", include_traceback=True, is_error=True)
            self.signals.error.emit(error_msg)
            log_message("[DOWNLOAD WORKER] Signal error.emit enviado")
            
        finally:
            log_message("[DOWNLOAD WORKER] Iniciando limpeza (finally block)")
            # Limpeza de forma mais segura
            try:
                if temp_dir and temp_dir.exists():
                    try:
                        shutil.rmtree(temp_dir)
                        log_message("[DOWNLOAD WORKER] Diretório temporário removido")
                    except PermissionError:
                        def remove_readonly(func, path, excinfo):
                            try:
                                os.chmod(path, stat.S_IWRITE)
                                func(path)
                            except:
                                pass
                        
                        try:
                            shutil.rmtree(temp_dir, onerror=remove_readonly)
                            log_message("[DOWNLOAD WORKER] Diretório temporário removido (com tratamento de readonly)")
                        except:
                            log_message("[DOWNLOAD WORKER] Não foi possível remover diretório temporário (será removido depois)")
                
                if filepath and os.path.exists(filepath):
                    try:
                        os.chmod(filepath, stat.S_IWRITE)
                        os.remove(filepath)
                        log_message("[DOWNLOAD WORKER] Arquivo temporário removido")
                    except Exception as e:
                        log_message(f"[DOWNLOAD WORKER] Erro ao remover arquivo: {e}")
            except Exception as e:
                log_message(f"[DOWNLOAD WORKER] Erro na limpeza: {e}")
            
            log_message("[DOWNLOAD WORKER] Worker concluído - FIM DO MÉTODO")
    
    def process_game_files(self, source_dir, steam_path):
        """Processa e move arquivos do jogo"""
        game_id = None
        game_name = None
        
        # Buscar ID na estrutura
        for item in os.listdir(source_dir):
            match = re.match(r"^(.*?)\s*\((\d+)\)$", item)
            if match:
                game_name = match.group(1).strip()
                game_id = match.group(2)
                break
        
        if not game_id:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    if file.lower().endswith(('.lua', '.st')):
                        match = re.search(r'(\d{5,7})', file)
                        if match:
                            game_id = match.group(1)
                            game_name = self.game_name or 'jogo'
                            break
                if game_id:
                    break
        
        if not game_id:
            raise ValueError("Não foi possível identificar o jogo")
        
        # Criar diretórios da Steam
        stplugin_dir = os.path.join(steam_path, "config", "stplug-in")
        depotcache_dir = os.path.join(steam_path, "config", "depotcache")
        StatsExport_dir = os.path.join(steam_path, "config", "StatsExport")
        
        os.makedirs(stplugin_dir, exist_ok=True)
        os.makedirs(depotcache_dir, exist_ok=True)
        os.makedirs(StatsExport_dir, exist_ok=True)
        
        moved_files = {
            'lua': [],
            'st': [],
            'bin': [],
            'manifests': []
        }
        
        # Mover arquivos de forma segura
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                try:
                    if file.lower().endswith('.lua'):
                        dest_path = os.path.join(stplugin_dir, file)
                        shutil.copy(file_path, dest_path)
                        moved_files['lua'].append(file)
                        
                    elif file.lower().endswith('.st'):
                        dest_path = os.path.join(stplugin_dir, file)
                        shutil.copy(file_path, dest_path)
                        moved_files['st'].append(file)
                        
                    elif file.lower().endswith('.bin'):
                        dest_path = os.path.join(StatsExport_dir, file)
                        shutil.copy(file_path, dest_path)
                        moved_files['bin'].append(file)
                        
                    elif file.lower().endswith('.manifest'):
                        dest_path = os.path.join(depotcache_dir, file)
                        shutil.copy(file_path, dest_path)
                        moved_files['manifests'].append(file)
                except Exception as e:
                    log_message(f"[DOWNLOAD WORKER] Erro ao copiar {file}: {e}")
                    continue
        
        total_moved = sum(len(files) for files in moved_files.values())
        if total_moved == 0:
            raise ValueError("Nenhum arquivo válido encontrado")
        
        log_message(f"[DOWNLOAD WORKER] Total de arquivos instalados: {total_moved}")
        return game_id, game_name, moved_files
    
    def register_game(self, game_name, game_id, moved_files):
        """Registra o jogo instalado"""
        try:
            registry_path = Path(os.getenv('APPDATA')) / "GamesStore" / "game_registry.json"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            
            registry = {}
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
            
            registry[game_name] = {
                "id": game_id,
                "install_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "paths": moved_files
            }
            
            with open(registry_path, 'w') as f:
                json.dump(registry, f, indent=4)
            
            log_message(f"[DOWNLOAD WORKER] Jogo registrado: {game_name} (ID: {game_id})")

        except Exception as e:
            log_message(f"Erro ao registrar jogo: {e}")


class DownloadThread(QThread):
    """Thread legada para downloads - usar DownloadWorker preferencialmente"""
    progress_updated = pyqtSignal(int)
    download_complete = pyqtSignal(bool)

    def __init__(self, url, filename):
        super().__init__()
        self.url = url
        self.filename = filename

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)
            
            self.download_complete.emit(True)
        except Exception as e:
            log_message(f"[DOWNLOAD THREAD] Erro no download: {str(e)}", is_error=True)
            self.download_complete.emit(False)
