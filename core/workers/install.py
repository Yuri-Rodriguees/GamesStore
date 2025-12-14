"""
Worker de instalação manual - ManualInstallWorker, ManualInstallWorkerSignals
"""
import os
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

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot as Slot

from utils import log_message
from core.utils.winrar import find_winrar, ensure_winrar_installed


class ManualInstallWorkerSignals(QObject):
    """Sinais para ManualInstallWorker"""
    progress = pyqtSignal(int)    
    status = pyqtSignal(str)      
    success = pyqtSignal(str)     
    error = pyqtSignal(str)       
    finished = pyqtSignal()


class ManualInstallWorker(QRunnable):
    """Worker para instalação manual de jogos"""
    
    def __init__(self, game_id, game_name, filepath, steam_path):
        super().__init__()
        self.game_id = game_id
        self.game_name = game_name
        self.filepath = filepath
        self.steam_path = steam_path
        self.signals = ManualInstallWorkerSignals()
    
    @Slot()
    def run(self):
        """Executa extração e instalação"""
        temp_dir = None
        
        try:
            self.signals.status.emit("Verificando arquivo...")
            self.signals.progress.emit(10)
            
            # Validar arquivo
            if not os.path.exists(self.filepath):
                raise FileNotFoundError(f"Arquivo não encontrado: {self.filepath}")
            
            # Criar diretório temporário
            self.signals.status.emit("Criando diretório temporário...")
            self.signals.progress.emit(20)
            
            temp_base = Path(tempfile.gettempdir()) / "GameStore_Manual"
            temp_base.mkdir(parents=True, exist_ok=True)
            temp_dir = temp_base / f"manual_{int(time.time())}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            log_message(f"Extraindo para: {temp_dir}")
            
            # Extrair arquivo
            self.signals.status.emit("Extraindo arquivos...")
            self.signals.progress.emit(30)
            
            if self.filepath.lower().endswith('.zip'):
                with zipfile.ZipFile(self.filepath, 'r') as zip_ref:
                    total_files = len(zip_ref.namelist())
                    for i, file in enumerate(zip_ref.namelist()):
                        zip_ref.extract(file, temp_dir)
                        progress = 30 + int((i / total_files) * 40)
                        self.signals.progress.emit(progress)
                log_message("Extração ZIP concluída")
            
            elif self.filepath.lower().endswith('.rar'):
                # Tentar encontrar WinRAR instalado
                winrar_path = find_winrar()
                
                # Se não encontrar, tentar instalar automaticamente
                if not winrar_path:
                    log_message("[MANUAL INSTALL] WinRAR não encontrado. Tentando instalar automaticamente...")
                    self.signals.status.emit("Instalando WinRAR...")
                    winrar_path = ensure_winrar_installed(self.signals)
                
                if not winrar_path:
                    raise Exception("WinRAR não encontrado e não foi possível instalar automaticamente")
                
                # Usar flags adequadas para .exe não fechar o processo pai
                is_frozen = getattr(sys, 'frozen', False)
                creation_flags = 0
                if is_frozen and sys.platform == 'win32':
                    creation_flags = subprocess.CREATE_NO_WINDOW
                
                subprocess.run(
                    [winrar_path, 'x', '-ibck', '-inul', str(self.filepath), str(temp_dir)],
                    check=True,
                    timeout=300,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.signals.progress.emit(70)
                log_message("Extração RAR concluída")
            
            # Instalar arquivos
            self.signals.status.emit("Instalando arquivos do jogo...")
            self.signals.progress.emit(75)
            
            moved_files = self.process_game_files(str(temp_dir), self.steam_path)
            
            self.signals.progress.emit(90)
            
            # Registrar jogo
            self.signals.status.emit("Registrando jogo...")
            self.register_game(self.game_name, self.game_id, moved_files)
            
            self.signals.progress.emit(100)
            
            self.signals.success.emit(
                f"{self.game_name} instalado com sucesso!\n\n"
                f"Reinicie a Steam para ver o jogo na biblioteca."
            )
            
        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            log_message(error_msg)
            import traceback
            traceback.print_exc()
            self.signals.error.emit(error_msg)
            
        finally:
            # Limpeza
            try:
                if temp_dir and temp_dir.exists():
                    def remove_readonly(func, path, excinfo):
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    
                    shutil.rmtree(temp_dir, onerror=remove_readonly)
                    log_message("Diretório temporário removido")
                    
            except Exception as e:
                log_message(f"Erro na limpeza: {e}")
            
            self.signals.finished.emit()
    
    def process_game_files(self, source_dir, steam_path):
        """Processa e move arquivos do jogo"""
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
        
        # Mover arquivos
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                if file.lower().endswith('.lua'):
                    dest_path = os.path.join(stplugin_dir, file)
                    shutil.copy2(file_path, dest_path)
                    moved_files['lua'].append(file)
                    
                elif file.lower().endswith('.st'):
                    dest_path = os.path.join(stplugin_dir, file)
                    shutil.copy2(file_path, dest_path)
                    moved_files['st'].append(file)
                    
                elif file.lower().endswith('.bin'):
                    dest_path = os.path.join(StatsExport_dir, file)
                    shutil.copy2(file_path, dest_path)
                    moved_files['bin'].append(file)
                    
                elif file.lower().endswith('.manifest'):
                    dest_path = os.path.join(depotcache_dir, file)
                    shutil.copy2(file_path, dest_path)
                    moved_files['manifests'].append(file)
        
        total_moved = sum(len(files) for files in moved_files.values())
        if total_moved == 0:
            raise ValueError("Nenhum arquivo válido encontrado no pacote")
        
        log_message(f"[MANUAL INSTALL] Total de arquivos instalados: {total_moved}")
        return moved_files
    
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
                "paths": moved_files,
                "install_type": "manual"
            }
            
            with open(registry_path, 'w') as f:
                json.dump(registry, f, indent=4)
            
            log_message(f"[MANUAL INSTALL] Jogo registrado: {game_name} (ID: {game_id})")
            
        except Exception as e:
            log_message(f"Erro ao registrar jogo: {e}")
            raise
