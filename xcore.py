

"""
Games Store - Core Module
==========================
Módulo principal da aplicação Games Store, responsável pela interface gráfica,
download e instalação de jogos, gerenciamento de biblioteca e integração com Steam.
"""
# Imports da biblioteca padrão
import os
import stat
import re
import sys
import json
import time
import shutil
import zipfile
import tempfile
import datetime
import subprocess
import platform
from pathlib import Path

# Imports de terceiros
import psutil
import requests

# Imports locais
import rc
import updater
from version import __version__
from utils import (
    get_safe_download_dir, get_log_directory, log_message,
    get_steam_directory, SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE, remove_readonly
)
from ui_components import TitleBar, CircularProgressBar

# Imports PyQt5 - Core
from PyQt5.QtCore import (
    Qt, QUrl, QSize, QMimeData, QPoint, QPropertyAnimation, QEasingCurve, 
    QTimer, pyqtSignal, QThread, QRect, QRectF, pyqtProperty, QEventLoop, 
    QObject, QRunnable, QThreadPool, QPointF, pyqtSlot as Slot
)

# Imports PyQt5 - GUI
from PyQt5.QtGui import (
    QFont, QFontMetrics, QIcon, QDesktopServices, QDragEnterEvent, QDropEvent, QColor, 
    QPalette, QPen, QLinearGradient, QPainter, QPainterPath, QPixmap, QCloseEvent
)

# Imports PyQt5 - Widgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QFrame, QScrollArea, QStackedWidget, QListWidget, QFileDialog, 
    QMessageBox, QGraphicsBlurEffect, QGraphicsColorizeEffect, 
    QGraphicsOpacityEffect, QProgressBar, QGraphicsDropShadowEffect,
    QDialog, QListWidgetItem, QSizePolicy, QCheckBox,
    QTextEdit, QComboBox, QSpinBox, QSystemTrayIcon, QMenu, QAction, QGridLayout
)

# ================================
# UTILITÁRIOS
# ================================

def find_winrar():
    """Encontra o caminho do WinRAR instalado"""
    winrar_paths = [
        r"C:\Program Files\WinRAR\WinRAR.exe",
        r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
    ]
    
    for path in winrar_paths:
        if os.path.exists(path):
            return path
    
    return None

def download_and_install_winrar(signals=None):
    """
    Baixa e instala o WinRAR PT-BR automaticamente
    
    Args:
        signals: Objeto com signals para emitir progresso (opcional)
    
    Returns:
        str: Caminho do WinRAR instalado ou None se falhar
    """
    try:
        log_message("[WINRAR] Iniciando download e instalação do WinRAR PT-BR...")
        
        # Detectar arquitetura do sistema
        is_64bit = platform.machine().endswith('64') or platform.architecture()[0] == '64bit'
        
        # URL do instalador WinRAR PT-BR (versão mais recente)
        # Tentar múltiplas URLs possíveis
        if is_64bit:
            winrar_urls = [
                "https://www.win-rar.com/fileadmin/winrar-versions/winrar-x64-611br.exe",
                "https://www.rarlab.com/rar/winrar-x64-611br.exe",
                "https://www.win-rar.com/fileadmin/winrar-versions/winrar-x64-700br.exe"  # Versão mais recente
            ]
        else:
            winrar_urls = [
                "https://www.win-rar.com/fileadmin/winrar-versions/wrar611br.exe",
                "https://www.rarlab.com/rar/wrar611br.exe"
            ]
        
        log_message(f"[WINRAR] Arquitetura detectada: {'64-bit' if is_64bit else '32-bit'}")
        
        # Diretório temporário para o instalador
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "winrar_installer.exe")
        
        # Emitir status se tiver signals
        if signals and hasattr(signals, 'status'):
            signals.status.emit("Baixando WinRAR PT-BR...")
        
        # Baixar instalador tentando múltiplas URLs
        download_success = False
        last_error = None
        
        for url_index, winrar_url in enumerate(winrar_urls):
            log_message(f"[WINRAR] Tentando URL {url_index + 1}/{len(winrar_urls)}: {winrar_url}")
            
            max_retries = 2  # Menos tentativas por URL já que temos múltiplas URLs
            for attempt in range(max_retries):
                try:
                    # Headers para simular navegador e evitar bloqueios
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        'Referer': 'https://www.win-rar.com/'
                    }
                    
                    response = requests.get(winrar_url, stream=True, timeout=60, headers=headers, allow_redirects=True)
                    response.raise_for_status()
                    
                    # Verificar se o conteúdo é realmente um executável
                    content_type = response.headers.get('content-type', '').lower()
                    if 'html' in content_type or 'text' in content_type:
                        log_message(f"[WINRAR] AVISO: URL retornou HTML ao invés de executável. Tentando próxima URL...")
                        break  # Tentar próxima URL
                    
                    # Verificar magic bytes do arquivo (MZ = executável Windows)
                    first_chunk = b''
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(installer_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                if not first_chunk:
                                    first_chunk = chunk[:2]
                                    # Verificar se começa com MZ (executável Windows)
                                    if first_chunk != b'MZ':
                                        log_message(f"[WINRAR] AVISO: Arquivo não parece ser um executável válido. Magic bytes: {first_chunk.hex()}")
                                        # Continuar mesmo assim, pode ser válido
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Emitir progresso se tiver signals
                                if signals and hasattr(signals, 'progress') and total_size > 0:
                                    progress = int((downloaded / total_size) * 100)
                                    signals.progress.emit(progress)
                    
                    # Verificar se o arquivo foi baixado completamente
                    file_size = os.path.getsize(installer_path)
                    
                    # Verificar tamanho mínimo (WinRAR geralmente tem pelo menos 2MB)
                    if file_size < 2 * 1024 * 1024:
                        log_message(f"[WINRAR] AVISO: Arquivo muito pequeno ({file_size} bytes). Tentando próxima URL...")
                        if os.path.exists(installer_path):
                            os.remove(installer_path)
                        break  # Tentar próxima URL
                    
                    # Verificar se o tamanho corresponde (com tolerância de 1%)
                    if total_size > 0:
                        size_diff = abs(file_size - total_size)
                        size_tolerance = total_size * 0.01  # 1% de tolerância
                        if size_diff > size_tolerance:
                            log_message(f"[WINRAR] AVISO: Tamanho não corresponde exatamente. Esperado: {total_size}, Obtido: {file_size}, Diferença: {size_diff}")
                            # Continuar mesmo assim se o arquivo for grande o suficiente
                    
                    # Verificar magic bytes do arquivo salvo
                    try:
                        with open(installer_path, 'rb') as f:
                            magic = f.read(2)
                            if magic == b'MZ':
                                download_success = True
                                log_message(f"[WINRAR] Download concluído com sucesso: {installer_path} ({file_size} bytes)")
                                break
                            else:
                                log_message(f"[WINRAR] AVISO: Arquivo não é executável válido. Magic bytes: {magic.hex()}")
                                if os.path.exists(installer_path):
                                    os.remove(installer_path)
                                if attempt < max_retries - 1:
                                    continue
                                break  # Tentar próxima URL
                    except Exception as e:
                        log_message(f"[WINRAR] Erro ao verificar arquivo: {e}")
                        if attempt < max_retries - 1:
                            continue
                        break
                    
                except Exception as e:
                    last_error = str(e)
                    log_message(f"[WINRAR] Erro no download da URL {url_index + 1} (tentativa {attempt + 1}/{max_retries}): {e}")
                    if os.path.exists(installer_path):
                        try:
                            os.remove(installer_path)
                        except:
                            pass
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Aguardar antes de tentar novamente
            
            if download_success:
                break
        
        if not download_success:
            raise Exception(f"Falha ao baixar o instalador do WinRAR de todas as URLs. Último erro: {last_error or 'Desconhecido'}")
        
        # Emitir status se tiver signals
        if signals and hasattr(signals, 'status'):
            signals.status.emit("Instalando WinRAR silenciosamente...")
        
        # Verificar se o arquivo existe e é válido antes de instalar
        if not os.path.exists(installer_path):
            raise Exception(f"Instalador não encontrado: {installer_path}")
        
        file_size = os.path.getsize(installer_path)
        if file_size < 2 * 1024 * 1024:
            raise Exception(f"Instalador corrompido ou incompleto: {file_size} bytes")
        
        log_message(f"[WINRAR] Instalador válido: {file_size} bytes")
        
        # Verificar permissões do arquivo
        try:
            # Tentar abrir o arquivo para verificar se não está bloqueado
            with open(installer_path, 'rb') as f:
                f.read(1)  # Ler apenas 1 byte para verificar
            log_message("[WINRAR] Arquivo acessível e legível")
        except PermissionError:
            log_message("[WINRAR] AVISO: Problema de permissão ao acessar arquivo")
            # Tentar remover atributo somente leitura se existir
            try:
                os.chmod(installer_path, stat.S_IWRITE | stat.S_IREAD)
                log_message("[WINRAR] Atributos de arquivo ajustados")
            except Exception as e:
                log_message(f"[WINRAR] Não foi possível ajustar atributos: {e}")
        except Exception as e:
            log_message(f"[WINRAR] AVISO ao verificar arquivo: {e}")
        
        # Instalar silenciosamente
        # Parâmetros: /S = Silent (instalação silenciosa)
        log_message("[WINRAR] Iniciando instalação silenciosa...")
        
        is_frozen = getattr(sys, 'frozen', False)
        creation_flags = 0
        if is_frozen and sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        
        # Tentar instalar com diferentes métodos
        install_success = False
        install_error = None
        
        # Método 1: Instalação direta
        try:
            log_message("[WINRAR] Tentando instalação direta...")
            proc = subprocess.Popen(
                [installer_path, '/S'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags if creation_flags else 0,
                shell=False
            )
            
            # Aguardar instalação (timeout de 3 minutos)
            return_code = proc.wait(timeout=180)
            
            if return_code == 0:
                install_success = True
                log_message("[WINRAR] Instalação concluída com sucesso (método direto)")
            else:
                log_message(f"[WINRAR] Instalação retornou código: {return_code}")
                
        except subprocess.TimeoutExpired:
            install_error = "Timeout na instalação"
            log_message(f"[WINRAR] {install_error}")
            try:
                proc.kill()
            except:
                pass
        except Exception as e:
            install_error = str(e)
            log_message(f"[WINRAR] Erro na instalação direta: {e}")
        
        # Método 2: Tentar com shell=True se o método 1 falhou
        if not install_success:
            try:
                log_message("[WINRAR] Tentando instalação com shell=True...")
                proc = subprocess.Popen(
                    f'"{installer_path}" /S',
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creation_flags if creation_flags else 0,
                    shell=True
                )
                
                return_code = proc.wait(timeout=180)
                
                if return_code == 0:
                    install_success = True
                    log_message("[WINRAR] Instalação concluída com sucesso (método shell)")
                else:
                    log_message(f"[WINRAR] Instalação com shell retornou código: {return_code}")
                    
            except subprocess.TimeoutExpired:
                install_error = "Timeout na instalação (método shell)"
                log_message(f"[WINRAR] {install_error}")
                try:
                    proc.kill()
                except:
                    pass
            except Exception as e:
                install_error = str(e)
                log_message(f"[WINRAR] Erro na instalação com shell: {e}")
        
        # Método 3: Tentar executar diretamente sem flags especiais se os anteriores falharam
        if not install_success:
            try:
                log_message("[WINRAR] Tentando instalação sem flags especiais...")
                proc = subprocess.Popen(
                    [installer_path, '/S'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL
                )
                
                return_code = proc.wait(timeout=180)
                
                if return_code == 0:
                    install_success = True
                    log_message("[WINRAR] Instalação concluída com sucesso (método simples)")
                else:
                    stdout, stderr = proc.communicate()
                    log_message(f"[WINRAR] Instalação retornou código: {return_code}")
                    if stderr:
                        log_message(f"[WINRAR] stderr: {stderr.decode('utf-8', errors='ignore')}")
                    
            except subprocess.TimeoutExpired:
                install_error = "Timeout na instalação (método simples)"
                log_message(f"[WINRAR] {install_error}")
                try:
                    proc.kill()
                except:
                    pass
            except Exception as e:
                install_error = str(e)
                log_message(f"[WINRAR] Erro na instalação simples: {e}")
        
        if not install_success:
            raise Exception(f"Falha na instalação do WinRAR: {install_error or 'Erro desconhecido'}")
        
        log_message("[WINRAR] Instalação concluída")
        
        # Limpar instalador temporário
        try:
            if os.path.exists(installer_path):
                os.remove(installer_path)
                log_message("[WINRAR] Instalador temporário removido")
        except Exception as e:
            log_message(f"[WINRAR] Erro ao remover instalador: {e}")
        
        # Aguardar um pouco para garantir que o WinRAR foi instalado
        time.sleep(2)
        
        # Verificar se foi instalado com sucesso
        winrar_path = find_winrar()
        if winrar_path:
            log_message(f"[WINRAR] WinRAR instalado com sucesso: {winrar_path}")
            if signals and hasattr(signals, 'status'):
                signals.status.emit("WinRAR instalado com sucesso!")
            return winrar_path
        else:
            log_message("[WINRAR] AVISO: WinRAR não encontrado após instalação")
            return None
            
    except subprocess.TimeoutExpired:
        log_message("[WINRAR] ERRO: Timeout na instalação")
        if signals and hasattr(signals, 'error'):
            signals.error.emit("Timeout ao instalar WinRAR")
        return None
    except Exception as e:
        log_message(f"[WINRAR] ERRO ao instalar WinRAR: {e}", include_traceback=True)
        if signals and hasattr(signals, 'error'):
            signals.error.emit(f"Erro ao instalar WinRAR: {str(e)}")
        return None

def ensure_winrar_installed(signals=None):
    """
    Garante que o WinRAR está instalado. Se não estiver, baixa e instala automaticamente.
    
    Args:
        signals: Objeto com signals para emitir progresso (opcional)
    
    Returns:
        str: Caminho do WinRAR ou None se não conseguir instalar
    """
    # Verificar se já está instalado
    winrar_path = find_winrar()
    if winrar_path:
        log_message(f"[WINRAR] WinRAR já instalado: {winrar_path}")
        return winrar_path
    
    # Se não estiver, instalar
    log_message("[WINRAR] WinRAR não encontrado. Iniciando instalação automática...")
    return download_and_install_winrar(signals)

# ================================
# WORKERS E THREADS
# ================================

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
                # log_message(f"Nome do jogo (Steam API): {game_name}")
                return game_name
            else:
                return f'jogo_{appid}'
                
        except Exception as e:
            # log_message(f"Erro ao buscar Steam API: {e}")
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
            
            # log_message(f"Salvando em: {filepath}")
            
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
            # log_message(f"Download concluído em {elapsed:.2f}s ({avg_speed_mbps:.2f} MB/s)")
            
            # FASE 2: EXTRAÇÃO E INSTALAÇÃO
            if self.steam_path:
                self.signals.status.emit("Extraindo arquivos...")
                self.signals.progress.emit(0)
                
                temp_base = Path(tempfile.gettempdir()) / "GameStore_Extract"
                temp_base.mkdir(parents=True, exist_ok=True)
                temp_dir = temp_base / f"extract_{int(time.time())}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                # log_message(f"Extraindo para: {temp_dir}")
                
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
                        # Tentar encontrar WinRAR instalado
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
            log_message(f"[DOWNLOAD WORKER] ERRO durante download/instalação: {error_msg}", include_traceback=True)
            import traceback
            traceback.print_exc()
            self.signals.error.emit(error_msg)
            log_message("[DOWNLOAD WORKER] Signal error.emit enviado")
            
        finally:
            log_message("[DOWNLOAD WORKER] Iniciando limpeza (finally block)")
            # Limpeza de forma mais segura
            try:
                if temp_dir and temp_dir.exists():
                    # Tentar remover de forma mais segura
                    try:
                        # Primeiro, tentar remover normalmente
                        shutil.rmtree(temp_dir)
                        log_message("[DOWNLOAD WORKER] Diretório temporário removido")
                    except PermissionError:
                        # Se falhar, tentar remover arquivos individualmente
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
                        # Tentar remover arquivo de forma segura
                        os.chmod(filepath, stat.S_IWRITE)
                        os.remove(filepath)
                        log_message("[DOWNLOAD WORKER] Arquivo temporário removido")
                    except Exception as e:
                        log_message(f"[DOWNLOAD WORKER] Erro ao remover arquivo: {e}")
            except Exception as e:
                log_message(f"[DOWNLOAD WORKER] Erro na limpeza: {e}")
                # Não propagar erro de limpeza
            
            # Não emitir signal finished - pode causar problemas no .exe
            # O dialog já é fechado pelo signal success
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
                # log_message(f"ID encontrado: {game_name} ({game_id})")
                break
        
        if not game_id:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    if file.lower().endswith(('.lua', '.st')):
                        match = re.search(r'(\d{5,7})', file)
                        if match:
                            game_id = match.group(1)
                            game_name = self.game_name or 'jogo'
                            # log_message(f"ID encontrado em arquivo: {file} -> {game_id}")
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
                        # Usar copy ao invés de copy2 para evitar problemas com metadados
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
                    # Continuar com outros arquivos mesmo se um falhar
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
            print(f"Erro no download: {str(e)}")
            self.download_complete.emit(False)

class DownloadProgressOverlay(QDialog):
    """Dialog de progresso de download com barra circular"""
    def __init__(self, parent, game_name):
        super().__init__(parent)
        self.game_name = game_name
        self._is_closing = False
        
        # Configurar dialog
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 12px;
                border: 2px solid #47D64E;
            }
        """)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Título
        title = QLabel(f"Baixando {game_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        # Barra de progresso circular (da ui_components)
        self.progress_bar = CircularProgressBar(self)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        # Status
        self.status_label = QLabel("Preparando download...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def on_download_success(self, message, filepath, game_id):
        """Callback de sucesso - fecha o dialog"""
        if self._is_closing:
            return
        
        try:
            self._is_closing = True
            
            # Atualizar UI
            self.status_label.setText("✅ Download concluído com sucesso!")
            self.status_label.setStyleSheet("color: #47D64E; font-weight: bold;")
            self.progress_bar.set_value(100)
            
            # Desconectar signals
            try:
                if hasattr(self, 'worker') and self.worker:
                    self.worker.signals.progress.disconnect()
                    self.worker.signals.status.disconnect()
                    self.worker.signals.success.disconnect()
                    self.worker.signals.error.disconnect()
            except:
                pass
            
            # Fechar dialog após pequeno delay
            QTimer.singleShot(500, self.accept)
            
        except Exception as e:
            log_message(f"[DOWNLOAD_PROGRESS] Erro em on_download_success: {e}")
            self.accept()
    
    def on_download_error(self, error_msg):
        """Callback de erro"""
        log_message(f"[DOWNLOAD_PROGRESS] Erro: {error_msg}")
        self.status_label.setText(f"❌ Erro: {error_msg}")
        self.status_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        QTimer.singleShot(2000, self.reject)

class DownloadScreen(QWidget):
    """Tela profissional de download com barra circular moderna"""
    download_finished = pyqtSignal(str, str)  # (message, game_id)
    
    def __init__(self, parent, game_id, game_name, download_url, steam_path):
        super().__init__(parent)
        self.parent_app = parent
        self.game_id = game_id
        self.game_name = game_name
        self._is_closing = False
        
        # Estilo da tela
        self.setStyleSheet("""
            QWidget {
                background-color: #1F1F1F;
            }
            QLabel {
                color: #E0E0E0;
            }
        """)
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignCenter)
        
        # Título do jogo
        title = QLabel(f"Baixando {game_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)
        
        # Barra de progresso circular
        self.progress_bar = CircularProgressBar(self)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        # Status
        self.status_label = QLabel("Preparando download...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.status_label)
        
        # Espaçamento
        layout.addStretch()
        
        # Botão Voltar (só aparece após download concluir)
        self.back_btn = QPushButton("← Voltar")
        self.back_btn.setFixedHeight(45)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 30px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-color: #47D64E;
            }
        """)
        self.back_btn.hide()  # Inicialmente oculto
        self.back_btn.clicked.connect(self.go_back)
        layout.addWidget(self.back_btn, alignment=Qt.AlignCenter)
        
        # Inicia worker
        self.worker = DownloadWorker(game_id, download_url, game_name, steam_path)
        self.worker.signals.progress.connect(self.progress_bar.setValue)
        self.worker.signals.status.connect(self.status_label.setText)
        self.worker.signals.success.connect(self.on_download_success)
        self.worker.signals.error.connect(self.on_download_error)
        
        parent.thread_pool.start(self.worker)
    
    def on_download_success(self, message, filepath, game_id):
        """Callback de sucesso - atualiza UI e pergunta sobre Steam"""
        log_message(f"[DOWNLOAD SCREEN] Download concluído - game_id={game_id}")
        
        if self._is_closing:
            return
        
        try:
            self._is_closing = True
            
            # Atualizar UI
            self.status_label.setText("✅ Download concluído com sucesso!")
            self.status_label.setStyleSheet("color: #47D64E; font-weight: bold;")
            self.progress_bar.setValue(100)
            
            # Mostrar botão voltar
            self.back_btn.show()
            
            # Desconectar signals
            try:
                if hasattr(self, 'worker') and self.worker:
                    self.worker.signals.progress.disconnect()
                    self.worker.signals.status.disconnect()
                    self.worker.signals.success.disconnect()
                    self.worker.signals.error.disconnect()
            except:
                pass
            
            # Emitir signal de download finalizado
            try:
                self.download_finished.emit(message, game_id)
            except:
                pass
            
            # Perguntar sobre reiniciar Steam após um pequeno delay
            QTimer.singleShot(500, lambda: self.ask_restart_steam())
            
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao processar sucesso: {e}", include_traceback=True)
    
    def ask_restart_steam(self):
        """Pergunta se deseja reiniciar a Steam"""
        try:
            log_message("[DOWNLOAD SCREEN] Perguntando sobre reiniciar Steam...")
            
            if self.parent_app and hasattr(self.parent_app, 'ask_restart_steam'):
                self.parent_app.ask_restart_steam()
            else:
                # Fallback: perguntar diretamente
                reply = QMessageBox.question(
                    self,
                    "Reiniciar Steam",
                    "O novo jogo foi instalado!\nDeseja reiniciar a Steam para aparecer na biblioteca?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    if self.parent_app and hasattr(self.parent_app, 'restart_steam'):
                        QTimer.singleShot(100, self.parent_app.restart_steam)
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao perguntar sobre Steam: {e}")
    
    def on_download_error(self, error_msg):
        """Callback de erro"""
        log_message(f"[DOWNLOAD SCREEN] Erro: {error_msg}")
        self.status_label.setText(f"❌ Erro: {error_msg}")
        self.status_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        self.back_btn.show()  # Mostrar botão voltar mesmo em caso de erro
        QMessageBox.critical(self, "Erro no Download", error_msg)
    
    def go_back(self):
        """Volta para a tela anterior"""
        try:
            log_message("[DOWNLOAD SCREEN] Voltando para tela anterior...")
            if self.parent_app:
                # Voltar para tela de jogos
                self.parent_app.pages.setCurrentIndex(1)  # tela_jogos
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao voltar: {e}")
               
class SpotlightOverlay(QWidget):
    """Overlay moderno que destaca um widget específico com animação de foco"""
    
    def __init__(self, parent, target_widget):
        super().__init__(parent)
        self.parent = parent
        self.target_widget = target_widget
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setGeometry(parent.rect())

        # Efeito de opacidade geral
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity.setDuration(600)
        self.opacity.setStartValue(0.0)
        self.opacity.setEndValue(1.0)
        self.opacity.start()

        # Timer de duração e fade out automático
        QTimer.singleShot(2500, self.fade_out)

        self.pulse = 0  # controle de brilho pulsante
        self.pulse_anim = QPropertyAnimation(self, b"pulsing")
        self.pulse_anim.setDuration(1200)
        self.pulse_anim.setStartValue(0)
        self.pulse_anim.setEndValue(1)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.start()

        self.show()
        self.raise_()

    # Property usada para animar o brilho pulsante
    @pyqtProperty(float)
    def pulsing(self):
        return self.pulse

    @pulsing.setter
    def pulsing(self, value):
        self.pulse = value
        self.update()

    def fade_out(self):
        self.fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade.setDuration(700)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.deleteLater)
        self.fade.start()

    def paintEvent(self, event):
        if not self.target_widget:
            return
        
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        
        # Fundo escuro translúcido
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))
        
        # Calcular posição e tamanho do widget alvo
        widget_screen_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
        widget_local = self.mapFromGlobal(widget_screen_pos)
        target_rect = QRect(widget_local, self.target_widget.size())
        target_rect = target_rect.adjusted(-10, -10, 10, 10)
        
        # Criar caminho com "recorte" para o foco
        highlight_path = QPainterPath()
        highlight_path.addRect(self.rect())
        
        spot_path = QPainterPath()
        spot_path.addRoundedRect(QRectF(target_rect), 14, 14)
        highlight_path = highlight_path.subtracted(spot_path)
        
        # Desenhar "buraco" de foco
        painter.fillPath(highlight_path, QColor(0, 0, 0, 220))
        
        # Desenhar borda iluminada e suave pulsante
        pulse_strength = 80 + int(40 * abs(self.pulse - 0.5) * 2)
        glow_color = QColor(71, 214, 78, pulse_strength)
        
        glow_pen = QPen(glow_color, 3)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(target_rect), 14, 14)

        # Pequeno texto informativo ("Novo jogo instalado!") acima
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.setPen(QColor(255, 255, 255, 230))
        msg_rect = QRectF(target_rect.left(), target_rect.top() - 35, target_rect.width(), 25)
        painter.drawText(msg_rect, Qt.AlignCenter, "🎮 Novo jogo instalado!")

class DetailsWorkerSignals(QObject):
    """Sinais para carregar detalhes do jogo"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

class DetailsWorker(QRunnable):
    """Worker para buscar detalhes do jogo"""
    
    def __init__(self, app_id, api_url_site):
        super().__init__()
        self.app_id = app_id
        self.api_url_site = api_url_site
        self.signals = DetailsWorkerSignals()
    
    @Slot()
    def run(self):
        try:
            url = f"{self.api_url_site}/detalhes-jogo/{self.app_id}"
            # print(f"[DEBUG] Carregando detalhes: {url}")
            
            response = requests.get(url, timeout=15)
            data = response.json()
            
            if data.get('status') == 'success':
                self.signals.finished.emit(data)
            else:
                self.signals.error.emit(data.get('message', 'Erro desconhecido'))
        except Exception as e:
            self.signals.error.emit(str(e))
            
class SearchWorkerSignals(QObject):
    """Sinais para o worker de busca"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

class SearchWorker(QRunnable):
    """Worker de busca"""
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = SearchWorkerSignals()
    
    @Slot()
    def run(self):
        try:
            print(f"[SearchWorker] Requisitando: {self.url}")
            
            response = requests.get(self.url, timeout=10)
            
            print(f"[SearchWorker] Status: {response.status_code}")
            print(f"[SearchWorker] Content-Type: {response.headers.get('content-type')}")
            print(f"[SearchWorker] Response length: {len(response.text)}")
            
            if not response.text or len(response.text.strip()) == 0:
                self.signals.error.emit("Resposta vazia da API")
                return
            
            if 'json' not in response.headers.get('content-type', ''):
                print(f"[SearchWorker] Resposta não é JSON: {response.text[:200]}")
                self.signals.error.emit("Resposta inválida (não é JSON)")
                return
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"[SearchWorker] Erro JSON: {e}")
                print(f"[SearchWorker] Response: {response.text[:500]}")
                self.signals.error.emit(f"Erro ao decodificar resposta: {e}")
                return
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                print(f"[SearchWorker] ✅ {len(jogos)} jogos encontrados")
                self.signals.finished.emit(jogos)
            else:
                error_msg = data.get('message', 'Erro desconhecido')
                print(f"[SearchWorker] ❌ Erro: {error_msg}")
                self.signals.error.emit(error_msg)
                
        except requests.exceptions.Timeout:
            print(f"[SearchWorker] ❌ Timeout")
            self.signals.error.emit("Tempo esgotado")
        except requests.exceptions.ConnectionError:
            print(f"[SearchWorker] ❌ Connection error")
            self.signals.error.emit("Erro de conexão")
        except Exception as e:
            print(f"[SearchWorker] ❌ Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(str(e))

class ImageLoaderSignals(QObject):
    """Sinais para carregamento de imagens"""
    finished = pyqtSignal(QPixmap)
    error = pyqtSignal()

class ImageLoader(QRunnable):
    """Worker otimizado para carregar imagens com cache e múltiplos fallbacks"""
    def __init__(self, urls, cache_key=None, max_size=(300, 300), parent_cache=None):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.cache_key = cache_key
        self.max_size = max_size
        self.parent_cache = parent_cache
        self.signals = ImageLoaderSignals()
    
    @Slot()
    def run(self):
        """Tenta carregar de múltiplas URLs com cache"""
        # Verificar cache primeiro se tiver chave
        if self.cache_key and self.parent_cache and self.cache_key in self.parent_cache:
            cached_pixmap = self.parent_cache[self.cache_key]
            if cached_pixmap and not cached_pixmap.isNull():
                self.signals.finished.emit(cached_pixmap)
                return
        
        # Tentar carregar de URLs
        for url in self.urls:
            try:
                # Timeout reduzido e headers para melhor performance
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br'
                }
                response = requests.get(url, timeout=8, headers=headers, stream=True)
                
                if response.status_code == 200:
                    # Carregar apenas primeiros bytes para verificar formato
                    content = response.content
                    
                    pixmap = QPixmap()
                    if pixmap.loadFromData(content):
                        # Redimensionar se necessário para economizar memória
                        if self.max_size and (pixmap.width() > self.max_size[0] or pixmap.height() > self.max_size[1]):
                            pixmap = pixmap.scaled(
                                self.max_size[0], self.max_size[1],
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                        
                        # Salvar no cache se tiver chave
                        if self.cache_key and self.parent_cache is not None:
                            # Limpar cache se exceder limite (FIFO)
                            # O tamanho máximo está no objeto pai (GameApp), não no dict
                            if '__parent_app' in self.parent_cache:
                                parent_app = self.parent_cache['__parent_app']
                                max_size = getattr(parent_app, '_max_cache_size', 100)
                                # Contar apenas chaves de imagens (excluindo __parent_app)
                                image_keys = [k for k in self.parent_cache.keys() if k != '__parent_app']
                                if len(image_keys) >= max_size:
                                    # Remover primeiro item (mais antigo), ignorando __parent_app
                                    for key in image_keys:
                                        del self.parent_cache[key]
                                        break
                            
                            self.parent_cache[self.cache_key] = pixmap
                        
                        self.signals.finished.emit(pixmap)
                        return
                    
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException:
                continue
            except Exception:
                continue
        
        self.signals.error.emit()

class GameDetailsLoaderSignals(QObject):
    """Sinais para carregar detalhes do jogo"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

class GameDetailsLoader(QRunnable):
    """Worker para buscar detalhes do jogo na Steam API"""
    def __init__(self, app_id, api_url_site):
        super().__init__()
        self.app_id = app_id
        self.api_url_site = api_url_site
        self.signals = GameDetailsLoaderSignals()
    
    @Slot()
    def run(self):
        try:
            # Buscar dados da Steam API
            steam_url = f"https://store.steampowered.com/api/appdetails?appids={self.app_id}&l=portuguese"
            response = requests.get(steam_url, timeout=10)
            data = response.json()
            
            if str(self.app_id) in data and data[str(self.app_id)].get('success'):
                game_data = data[str(self.app_id)]['data']
                
                # Verificar disponibilidade na sua API
                availability = self.check_availability()
                
                details = {
                    'name': game_data.get('name', 'Jogo'),
                    'short_description': game_data.get('short_description', 'Sem descrição'),
                    'header_image': game_data.get('header_image', ''),
                    'screenshots': [s.get('path_full') for s in game_data.get('screenshots', [])[:3]],
                    'genres': [g.get('description') for g in game_data.get('genres', [])],
                    'developers': game_data.get('developers', []),
                    'publishers': game_data.get('publishers', []),
                    'release_date': game_data.get('release_date', {}).get('date', 'N/A'),
                    'price': game_data.get('price_overview', {}).get('final_formatted', 'Grátis'),
                    'available_download': availability['available'],
                    'keys_count': availability['keys_count']
                }
                
                self.signals.finished.emit(details)
            else:
                self.signals.error.emit("Jogo não encontrado na Steam")
                
        except Exception as e:
            self.signals.error.emit(f"Erro ao carregar: {str(e)}")
    
    def check_availability(self):
        """Verifica se o jogo está disponível na sua API"""
        try:
            url = f"{self.api_url_site}/verificar-jogo/{self.app_id}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'available': True,
                    'keys_count': data.get('keys_disponiveis', 0)
                }
        except:
            pass
        
        return {'available': False, 'keys_count': 0}

class GameDetailsScreen(QWidget):
    """Tela de detalhes do jogo (convertida de modal para tela real)"""
    
    def __init__(self, parent, game_id, details):
        super().__init__(parent)
        self.game_id = game_id
        self.details = details
        self.parent_app = parent
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Container principal com fundo
        self.main_container = QFrame(self)
        self.main_container.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
            }
        """)
        
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Setup do conteúdo
        self.setup_screen_content(container_layout)
        
        layout.addWidget(self.main_container)
    
    def setup_screen_content(self, layout):
        """Monta o conteúdo da tela"""
        details = self.details
        game_id = self.game_id
        
        # Header
        header = QFrame()
        header.setFixedHeight(300)
        header.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
            }
        """)
        
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_image = QLabel()
        header_image.setFixedSize(1200, 300)
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        
        if details.get('background') or details.get('header_image'):
            bg_url = details.get('background') or details.get('header_image')
            cache_key = f"game_details_header_{self.game_id}"
            loader = ImageLoader(
                bg_url,
                cache_key=cache_key,
                max_size=(1250, 350),
                parent_cache=self.parent_app.image_cache
            )
            def on_header_loaded(pixmap):
                try:
                    if header_image and not pixmap.isNull():
                        scaled = pixmap.scaled(
                            1200, 300,
                            Qt.KeepAspectRatioByExpanding,
                            Qt.SmoothTransformation
                        )
                        header_image.setPixmap(scaled)
                except (RuntimeError, AttributeError):
                    pass
            
            loader.signals.finished.connect(on_header_loaded)
            loader.signals.error.connect(lambda: None)
            self.parent_app.thread_pool.start(loader)
        
        header_layout.addWidget(header_image)
        
        overlay = QLabel(header)
        overlay.setGeometry(0, 0, 1200, 300)
        overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 transparent,
                stop:1 rgba(26, 26, 26, 0.9)
            );
        """)
        
        # Botão voltar
        back_btn = QPushButton("← Voltar", header)
        back_btn.setFixedSize(100, 40)
        back_btn.move(20, 10)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(71, 214, 78, 0.8);
            }
        """)
        back_btn.clicked.connect(lambda: self.parent_app.pages.setCurrentIndex(1))
        
        layout.addWidget(header)
        
        # Scroll de conteúdo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #1a1a1a;
            }
            QScrollBar::handle:vertical {
                background: #47D64E;
                border-radius: 4px;
            }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(15)
        
        # Título
        title = QLabel(details.get('nome', 'Jogo'))
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)
        
        # Info horizontal
        info_layout = QHBoxLayout()
        
        id_label = QLabel(f"🎮 Steam ID: {game_id}")
        id_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        
        disponivel = details.get('disponivel_download', False)
        tem_chaves = details.get('tem_chaves', False)
        qtd_chaves = details.get('quantidade_chaves', 0)
        
        if disponivel:
            avail_label = QLabel("✔️ Disponível para Download")
            avail_label.setStyleSheet("color: #47D64E; font-size: 13px; font-weight: bold;")
            # Informativo sobre chaves (opcional)
            if tem_chaves and qtd_chaves > 0:
                keys_label = QLabel(f"Chaves extras: {qtd_chaves}")
                keys_label.setStyleSheet("font-size: 11px; color: #bbbbbb; margin-left:12px;")
                info_layout.addWidget(keys_label)
        else:
            avail_label = QLabel("❌ Não disponível")
            avail_label.setStyleSheet("color: #ff4444; font-size: 13px; font-weight: bold;")

        info_layout.addWidget(id_label)
        info_layout.addWidget(avail_label)
        info_layout.addStretch()
        
        # Descrição
        desc = QLabel(details.get('descricao', 'Sem descrição'))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 13px;")
        
        # Informações extras
        info_grid = QVBoxLayout()
        info_grid.setSpacing(8)
        
        if details.get('generos'):
            generos = ', '.join(details['generos']) if isinstance(details['generos'], list) else details['generos']
            genres_label = QLabel(f"📂 Gêneros: {generos}")
            genres_label.setStyleSheet("color: white; font-size: 12px;")
            info_grid.addWidget(genres_label)
        
        if details.get('desenvolvedores'):
            devs = ', '.join(details['desenvolvedores']) if isinstance(details['desenvolvedores'], list) else details['desenvolvedores']
            dev_label = QLabel(f"👨‍💻 Desenvolvedores: {devs}")
            dev_label.setStyleSheet("color: white; font-size: 12px;")
            info_grid.addWidget(dev_label)
        
        if details.get('data_lancamento'):
            release_label = QLabel(f"📅 Lançamento: {details['data_lancamento']}")
            release_label.setStyleSheet("color: white; font-size: 12px;")
            info_grid.addWidget(release_label)
        
        content_layout.addWidget(title)
        content_layout.addLayout(info_layout)
        content_layout.addWidget(desc)
        content_layout.addSpacing(10)
        content_layout.addLayout(info_grid)
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        # Footer com botões
        footer = QFrame()
        footer.setFixedHeight(90)
        footer.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 transparent,
                    stop:1 rgba(26, 26, 26, 0.95)
                );
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(30, 15, 30, 15)
        footer_layout.setSpacing(15)
        
        # Botão download
        download_btn = QPushButton("⬇️ Baixar Agora")
        download_btn.setFixedHeight(55)
        download_btn.setCursor(Qt.PointingHandCursor)
        
        if disponivel:
            download_btn.setText("⬇️ Baixar Agora")
            download_btn.setEnabled(True)
            download_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #47D64E, stop:1 #5ce36c);
                    color: #1F1F1F;
                    border: none;
                    border-radius: 10px;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0 30px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5ce36c, stop:1 #47D64E);
                }
            """)
            download_btn.clicked.connect(lambda: self.parent_app.start_download_from_api(game_id, details.get('nome', 'Jogo')))
        else:
            download_btn.setText("❌ Não Disponível")
            download_btn.setEnabled(False)
            download_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(100, 100, 100, 0.3);
                    color: rgba(255, 255, 255, 0.4);
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0 30px;
                }
            """)
        
        # Botão Steam
        steam_btn = QPushButton("🎮 Ver na Steam")
        steam_btn.setFixedHeight(55)
        steam_btn.setCursor(Qt.PointingHandCursor)
        steam_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                padding: 0 30px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-color: #47D64E;
            }
        """)
        steam_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{game_id}"))
        )
        
        footer_layout.addWidget(download_btn, 2)
        footer_layout.addWidget(steam_btn, 1)
        
        layout.addWidget(footer, 0)
    

class ManualInstallScreen(QWidget):
    """Tela de instalação manual de jogo - Versão simplificada"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent_app = parent
        self.selected_file_path = None
        
        # Layout principal simples
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        
        # Botão voltar
        back_btn = QPushButton("← Voltar")
        back_btn.setFixedSize(100, 40)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(71, 214, 78, 0.8);
            }
        """)
        def go_back():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
            except Exception as e:
                log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao voltar: {e}")
        
        back_btn.clicked.connect(go_back)
        layout.addWidget(back_btn)
        
        # Título
        title = QLabel("📥 Instalação Manual de Jogo")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Instruções
        instructions = QLabel(
            "Selecione um arquivo .ZIP ou .RAR no formato:\n"
            "Nome do Jogo (ID).zip\n\n"
            "Exemplo: GTA V (271590).rar"
        )
        instructions.setFont(QFont("Arial", 13))
        instructions.setStyleSheet("color: rgba(255, 255, 255, 0.7); padding: 20px;")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Frame de seleção de arquivo
        file_frame = QFrame()
        file_frame.setFixedHeight(120)
        file_frame.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 12px;
                border: 2px solid #333;
            }
        """)
        
        file_layout = QVBoxLayout(file_frame)
        file_layout.setAlignment(Qt.AlignCenter)
        
        self.file_label = QLabel("📁 Nenhum arquivo selecionado")
        self.file_label.setFont(QFont("Arial", 12))
        self.file_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setWordWrap(True)
        
        file_layout.addWidget(self.file_label)
        layout.addWidget(file_frame)
        
        # Botão de seleção
        btn_select = QPushButton("🔍 Selecionar Arquivo")
        btn_select.setFixedHeight(50)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 2px solid #47D64E;
                border-radius: 25px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #333333;
                border-color: #5ce36c;
            }
        """)
        btn_select.clicked.connect(self.select_file)
        layout.addWidget(btn_select)
        
        layout.addStretch()
        
        # Botões de ação
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedSize(150, 50)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: 25px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #333;
            }
        """)
        def cancel_action():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
            except Exception as e:
                log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao cancelar: {e}")
        
        btn_cancel.clicked.connect(cancel_action)
        
        btn_install = QPushButton("🚀 Instalar")
        btn_install.setFixedSize(150, 50)
        btn_install.setCursor(Qt.PointingHandCursor)
        btn_install.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                color: #1F1F1F;
                border: none;
                border-radius: 25px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5ce36c,
                    stop:1 #6ff57d
                );
            }
            QPushButton:disabled {
                background: #333;
                color: #666;
            }
        """)
        btn_install.clicked.connect(self.start_install)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_cancel)
        buttons_layout.addWidget(btn_install)
        
        layout.addLayout(buttons_layout)
    
    def select_file(self, checked=False):
        """Abre dialog para selecionar arquivo"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar Arquivo de Jogo",
                os.path.expanduser("~"),
                "Arquivos de Jogo (*.zip *.rar);;Todos os Arquivos (*.*)",
                options=QFileDialog.DontUseNativeDialog
            )
            
            if file_path:
                self.selected_file_path = file_path
                filename = os.path.basename(file_path)
                if hasattr(self, 'file_label') and self.file_label:
                    self.file_label.setText(f"✅ {filename}")
                    self.file_label.setStyleSheet("color: #47D64E;")
                    
                    # Validar formato
                    match = re.match(r"^(.+?)\s*\((\d+)\)\.(zip|rar)$", filename, re.IGNORECASE)
                    if not match:
                        self.file_label.setText(f"⚠️ {filename}\n(Formato inválido)")
                        self.file_label.setStyleSheet("color: #ff9500;")
        except Exception as e:
            log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao selecionar arquivo: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao selecionar arquivo:\n{str(e)}")
    
    def start_install(self, checked=False):
        """Inicia instalação manual"""
        try:
            if not self.selected_file_path:
                QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro!")
                return
            
            # Verificar se parent_app existe e tem os métodos necessários
            if not self.parent_app:
                QMessageBox.critical(self, "Erro", "Aplicação principal não disponível")
                return
            
            # Voltar para tela de jogos
            if hasattr(self.parent_app, 'pages'):
                self.parent_app.pages.setCurrentIndex(1)
            
            # Iniciar instalação
            if hasattr(self.parent_app, 'install_manual_game'):
                self.parent_app.install_manual_game(self.selected_file_path)
            else:
                QMessageBox.critical(self, "Erro", "Método de instalação não disponível")
        except Exception as e:
            log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao iniciar instalação: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar instalação:\n{str(e)}")

class InstalledGameScreen(QWidget):
    """Tela para gerenciar jogo instalado (convertida de modal para tela)"""
    
    def __init__(self, parent, game_name, game_info):
        super().__init__()
        try:
            self.game_name = game_name
            self.game_info = game_info
            self.parent_app = parent
            self.game_id = game_info.get('id', '')
            
            # Layout principal
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # Container principal com fundo
            self.main_container = QFrame(self)
            self.main_container.setStyleSheet("""
                QFrame {
                    background: #1a1a1a;
                }
            """)
            
            container_layout = QVBoxLayout(self.main_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            self.setup_content(container_layout)
            
            layout.addWidget(self.main_container)
            
        except Exception as e:
            log_message(f"[INSTALLED_GAME_SCREEN] Erro ao criar tela: {e}", include_traceback=True)
            # Criar tela de erro simples
            error_layout = QVBoxLayout(self)
            error_label = QLabel(f"Erro ao carregar tela do jogo:\n{str(e)}")
            error_label.setStyleSheet("color: #FF4444; padding: 20px;")
            error_label.setAlignment(Qt.AlignCenter)
            error_layout.addWidget(error_label)
            
            back_btn = QPushButton("← Voltar")
            back_btn.clicked.connect(lambda: parent.pages.setCurrentIndex(1) if hasattr(parent, 'pages') else None)
            error_layout.addWidget(back_btn)
    
    def setup_content(self, container_layout):
        """Configura o conteúdo da tela"""
        # Header
        header = QFrame()
        header.setFixedHeight(300)
        header.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
            }
        """)
        
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header com botão voltar
        header_top = QFrame()
        header_top.setFixedHeight(60)
        header_top.setStyleSheet("""
            QFrame {
                background: transparent;
            }
        """)
        
        header_top_layout = QHBoxLayout(header_top)
        header_top_layout.setContentsMargins(20, 10, 20, 10)
        
        # Botão voltar
        close_btn = QPushButton("✕", header_top)
        close_btn.setFixedSize(40, 40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(71, 214, 78, 0.8);
            }
        """)
        def go_back():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
                    # Recarregar jogos instalados
                    if hasattr(self.parent_app, 'load_installed_games'):
                        self.parent_app.load_installed_games()
            except Exception as e:
                log_message(f"[INSTALLED_GAME_SCREEN] Erro ao voltar: {e}")
        
        close_btn.clicked.connect(go_back)
        header_top_layout.addWidget(close_btn)
        header_top_layout.addStretch()
        
        header_layout.addWidget(header_top)
        
        # Imagem do header
        header_image = QLabel()
        header_image.setFixedSize(1200, 240)
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        
        # Carregar imagem com cache
        if self.game_id:
            cache_key = f"header_{self.game_id}"
            url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.game_id}/header.jpg"
            
            loader = ImageLoader(
                url,
                cache_key=cache_key,
                max_size=(1250, 350),
                parent_cache=self.parent_app.image_cache
            )
            
            def on_header_loaded(pixmap):
                try:
                    if header_image and not pixmap.isNull():
                        scaled = pixmap.scaled(
                            1200, 240,
                            Qt.KeepAspectRatioByExpanding,
                            Qt.SmoothTransformation
                        )
                        header_image.setPixmap(scaled)
                except (RuntimeError, AttributeError):
                    pass
            
            loader.signals.finished.connect(on_header_loaded)
            loader.signals.error.connect(lambda: None)
            self.parent_app.thread_pool.start(loader)
        
        header_layout.addWidget(header_image)
        
        container_layout.addWidget(header)
        
        # Conteúdo
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(50, 50, 50, 50)
        content_layout.setSpacing(20)
        
        # Título
        title = QLabel(self.game_name)
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)
        
        # Status instalado
        status = QLabel("✅ Jogo Instalado")
        status.setFont(QFont("Arial", 16))
        status.setStyleSheet("color: #47D64E;")
        
        # Informações
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)
        
        id_label = QLabel(f"🎮 Steam ID: {self.game_id}")
        id_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 14px;")
        
        install_date = self.game_info.get('install_date', 'N/A')
        date_label = QLabel(f"📅 Instalado em: {install_date}")
        date_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 14px;")
        
        # Contagem de arquivos
        manifests_count = len(self.game_info.get('paths', {}).get('manifests', []))
        files_label = QLabel(f"📦 {manifests_count} manifesto{'s' if manifests_count != 1 else ''}")
        files_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 14px;")
        
        info_layout.addWidget(id_label)
        info_layout.addWidget(date_label)
        info_layout.addWidget(files_label)
        
        content_layout.addWidget(title)
        content_layout.addWidget(status)
        content_layout.addSpacing(20)
        content_layout.addLayout(info_layout)
        content_layout.addStretch()
        
        container_layout.addWidget(content, 1)
        
        # Footer com botões
        footer = QFrame()
        footer.setFixedHeight(100)
        footer.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
            }
        """)
        
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(50, 20, 50, 20)
        footer_layout.setSpacing(20)
        
        # Botão Jogar
        play_btn = QPushButton("▶️ Jogar")
        play_btn.setFixedHeight(60)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #47D64E, stop:1 #5ce36c);
                color: #1F1F1F;
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                padding: 0 40px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5ce36c, stop:1 #47D64E);
            }
        """)
        play_btn.clicked.connect(self.launch_game)
        
        # Botão Desinstalar
        uninstall_btn = QPushButton("🗑️ Desinstalar")
        uninstall_btn.setFixedHeight(60)
        uninstall_btn.setCursor(Qt.PointingHandCursor)
        uninstall_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 68, 68, 0.2);
                color: #ff4444;
                border: 2px solid rgba(255, 68, 68, 0.5);
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
                padding: 0 40px;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.3);
                border-color: #ff4444;
            }
        """)
        uninstall_btn.clicked.connect(self.uninstall_game)
        
        footer_layout.addStretch()
        footer_layout.addWidget(play_btn)
        footer_layout.addWidget(uninstall_btn)
        footer_layout.addStretch()
        
        container_layout.addWidget(footer)
    
    def launch_game(self, checked=False):
        """Lança o jogo via Steam"""
        try:
            steam_url = f"steam://rungameid/{self.game_id}"
            QDesktopServices.openUrl(QUrl(steam_url))
            print(f"[LAUNCH] Abrindo jogo: {self.game_name} (ID: {self.game_id})")
        except Exception as e:
            print(f"[LAUNCH] Erro: {e}")
            QMessageBox.warning(self.parent_app, "Erro", f"Não foi possível iniciar o jogo:\n{e}")
    
    def uninstall_game(self, checked=False):
        """Desinstala o jogo (remove json e arquivos físicos)"""
        reply = QMessageBox.question(
            self.parent_app,
            "Confirmar Desinstalação",
            f"Tem certeza que deseja desinstalar '{self.game_name}'?\n\nIsso removerá todos os arquivos do jogo.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                registry_path = Path(os.getenv('APPDATA')) / "GamesStore" / "game_registry.json"
                steam_path = self.parent_app.steam_path
                
                with open(registry_path, 'r', encoding='utf-8') as f:
                    games_data = json.load(f)
                
                # Remover arquivos vinculados
                if self.game_name in games_data:
                    file_paths = games_data[self.game_name].get("paths", {})
                    
                    dirs = {
                        "lua": os.path.join(steam_path, "config", "stplug-in"),
                        "st": os.path.join(steam_path, "config", "stplug-in"),
                        "bin": os.path.join(steam_path, "config", "stplug-in"),
                        "manifests": os.path.join(steam_path, "config", "depotcache"),
                    }
                    
                    # Remove arquivos
                    for category, files in file_paths.items():
                        base_dir = dirs.get(category)
                        if base_dir and files:
                            for filename in files:
                                file_path = os.path.join(base_dir, filename)
                                try:
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                except Exception as remove_err:
                                    print(f"[UNINSTALL] Não foi possível remover {file_path}: {remove_err}")
                    
                    # Remove do registro
                    del games_data[self.game_name]

                    with open(registry_path, 'w', encoding='utf-8') as f:
                        json.dump(games_data, f, indent=4, ensure_ascii=False)
                    
                    QMessageBox.information(
                        self.parent_app, "Sucesso",
                        f"'{self.game_name}' foi desinstalado com sucesso!"
                    )
                    
                    # Voltar para tela de jogos e recarregar
                    if hasattr(self.parent_app, 'pages'):
                        self.parent_app.pages.setCurrentIndex(1)
                        if hasattr(self.parent_app, 'load_installed_games'):
                            self.parent_app.load_installed_games()
            except Exception as e:
                print(f"[UNINSTALL] Erro: {e}")
                QMessageBox.critical(self.parent_app, "Erro", f"Erro ao desinstalar:\n{e}")
        
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
        
        log_message(f"[DOWNLOAD WORKER] Total de arquivos instalados: {total_moved}")
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
            
            log_message(f"[DOWNLOAD WORKER] Jogo registrado: {game_name} (ID: {game_id})")
            
        except Exception as e:
            log_message(f"Erro ao registrar jogo: {e}")
            raise

class ManualInstallProgressOverlay(QDialog):
    """Overlay de progresso para instalação manual"""
    
    def __init__(self, parent, game_id, game_name, filepath, steam_path):
        super().__init__(parent)
        self.game_id = game_id
        self.game_name = game_name
        self.filepath = filepath
        self.steam_path = steam_path
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setFixedSize(500, 350)
        
        self.setup_ui()
        
        # Iniciar instalação
        QTimer.singleShot(100, self.start_installation)
    
    def setup_ui(self):
        """Configura interface do overlay"""
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 16px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        
        # Título
        title = QLabel(f"Instalando {self.game_name}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        
        # Status
        self.status_label = QLabel("Preparando instalação...")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(30)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #232323;
                border: 2px solid #333;
                border-radius: 15px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                border-radius: 13px;
            }
        """)
        self.progress_bar.setValue(0)
        
        # Detalhes
        self.details_label = QLabel(f"ID: {self.game_id}")
        self.details_label.setFont(QFont("Arial", 10))
        self.details_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        self.details_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.details_label)
    
    def start_installation(self):
        """Inicia processo de instalação"""
        worker = ManualInstallWorker(
            self.game_id, 
            self.game_name, 
            self.filepath, 
            self.steam_path
        )
        
        worker.signals.progress.connect(self.update_progress)
        worker.signals.status.connect(self.update_status)
        worker.signals.success.connect(self.on_success)
        worker.signals.error.connect(self.on_error)
        
        QThreadPool.globalInstance().start(worker)
    
    def update_progress(self, value):
        """Atualiza barra de progresso"""
        self.progress_bar.setValue(value)
    
    def update_status(self, status):
        """Atualiza mensagem de status"""
        self.status_label.setText(status)
    
    def on_success(self, message):
        """Callback de sucesso"""
        self.accept()
        QMessageBox.information(self.parent(), "✅ Instalação Concluída", message)
        self.parent().load_installed_games()
        
        # Perguntar sobre reiniciar Steam
        QTimer.singleShot(500, self.parent().ask_restart_steam)
    
    def on_error(self, error_msg):
        """Callback de erro"""
        self.reject()
        QMessageBox.critical(self.parent(), "❌ Erro na Instalação", 
            f"Falha ao instalar o jogo:\n\n{error_msg}")
        
class GameApp(QWidget):
    """Aplicação principal do Games Store Launcher"""
    
    def __init__(self):
        super().__init__()
        
        self.secret_key = SECRET_KEY
        self.api_url = API_URL
        self.api_url_site = API_URL_SITE
        self.auth_code = AUTH_CODE
        
        # Cache de imagens otimizado (limite de 100 imagens)
        self.image_cache = {}
        self.image_cache['__parent_app'] = self  # Referência para acessar _max_cache_size
        self._max_cache_size = 100  # Limite do cache
        
        # Thread pool único para todas as operações assíncronas
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        
        # Configurar janela
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(200, 200, 1200, 800)
        self.setFixedSize(1200, 800)
        self.setStyleSheet("background: #1a1a1a; color: white;")
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        self.setWindowTitle(f"Games Store v{__version__}")
        
        # Variáveis de controle
        self.search_thread = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(500)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.old_pos = None
        self.setAcceptDrops(True)
        self.drag_over = False
        self.steam_path = None
        self.selected_file_path = None
        
        # Inicializar interface
        self.init_ui()
        
        # Carregar Steam
        QTimer.singleShot(0, self.get_steam_directory)
    
    # ========================================================================
    # SEÇÃO 1: INTERFACE DO USUÁRIO (UI)
    # ========================================================================
    
    def init_ui(self):
        """Inicializa a interface completa"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title Bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        # Container principal
        content = QHBoxLayout()
        
        # Menu lateral
        menu = self.create_sidebar()
        content.addWidget(menu, 1)
        
        # Páginas
        self.pages = QStackedWidget()
        self.tela_home = QWidget()
        self.tela_jogos = QWidget()
        self.tela_dlcs = QWidget()
        self.tela_manual_install = ManualInstallScreen(self)  # Criar na inicialização
        self.tela_download = None  # Será criada quando necessário
        self.tela_detalhes = None  # Será criada quando necessário
        self.tela_installed_game = None  # Será criada quando necessário
        
        self.pages.addWidget(self.tela_home)
        self.pages.addWidget(self.tela_jogos)
        self.pages.addWidget(self.tela_dlcs)
        self.manual_install_index = self.pages.addWidget(self.tela_manual_install)
        
        content.addWidget(self.pages, 4)
        main_layout.addLayout(content)
        
        # Setup das páginas
        self.setup_home()
        self.setup_jogos()
        self.setup_dlcs()
    
    def create_sidebar(self):
        """Cria menu lateral moderno"""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border-right: 1px solid #333;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setAlignment(Qt.AlignTop)
        
        # Botões do menu
        self.btn_home = self.create_menu_button("🏠 Home", 0)
        self.btn_games = self.create_menu_button("🎮 Jogos", 1)
        self.btn_dlcs = self.create_menu_button("📦 DLCs", 2)
        
        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_games)
        layout.addWidget(self.btn_dlcs)
        layout.addStretch()
        
        return sidebar
    
    def create_menu_button(self, text, page_index):
        """Cria botão estilizado do menu"""
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: white;
                padding: 15px 20px;
                font-size: 15px;
                font-weight: 600;
                border-radius: 8px;
                text-align: left;
                border: none;
            }
            QPushButton:hover {
                background: #2a2a2a;
            }
            QPushButton:pressed {
                background: #47D64E;
                color: #000;
            }
        """)
        btn.setMinimumHeight(50)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.pages.setCurrentIndex(page_index))
        return btn
    
    # ========================================================================
    # SEÇÃO 2: HOME PAGE
    # ========================================================================
    
    def setup_home(self):
        """Setup com apenas uma seção de jogos"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Widgets ocultos
        self.list_widget = QListWidget()
        self.list_widget.setVisible(False)
        
        if not hasattr(self, 'search_input'):
            self.search_input = QLineEdit()
        
        # Header
        header = self.create_modern_header()
        layout.addWidget(header)
        
        # Hero Banner
        self.hero_banner = self.create_hero_banner()
        layout.addWidget(self.hero_banner)
        
        # Container de resultados de busca
        self.search_results_main_container = QScrollArea()
        self.search_results_main_container.setWidgetResizable(True)
        self.search_results_main_container.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.search_results_main_container.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #1a1a1a;
            }
            QScrollBar::handle:vertical {
                background: #47D64E;
                border-radius: 4px;
            }
        """)
        
        search_content = QWidget()
        self.search_results_main_layout = QVBoxLayout(search_content)
        self.search_results_main_layout.setContentsMargins(30, 20, 30, 20)
        self.search_results_main_layout.setSpacing(20)
        
        self.search_results_title = QLabel()
        self.search_results_title.setFont(QFont("Arial", 22, QFont.Bold))
        self.search_results_title.setStyleSheet("color: white; padding: 10px 0;")
        self.search_results_main_layout.addWidget(self.search_results_title)
        
        self.search_cards_container = QWidget()
        self.search_cards_layout = QGridLayout(self.search_cards_container)
        self.search_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.search_cards_layout.setSpacing(20)
        self.search_cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.search_results_main_layout.addWidget(self.search_cards_container)
        
        self.search_results_main_layout.addStretch()
        
        self.search_results_main_container.setWidget(search_content)
        self.search_results_main_container.setVisible(False)
        
        layout.addWidget(self.search_results_main_container)

        self.games_scroll_area = QScrollArea()
        self.games_scroll_area.setWidgetResizable(True)
        self.games_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.games_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #47D64E;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5ce36c;
            }
        """)
        
        games_container = QWidget()
        games_layout = QVBoxLayout(games_container)
        games_layout.setContentsMargins(20, 20, 20, 20)
        games_layout.setSpacing(30)
        
        self.all_games_container = QWidget()
        self.all_games_section = self.create_game_section("🎮 Todos os Jogos", self.all_games_container)
        
        games_layout.addWidget(self.all_games_section)
        games_layout.addStretch()
        
        self.games_scroll_area.setWidget(games_container)
        layout.addWidget(self.games_scroll_area)
        
        self.tela_home.setLayout(layout)
        
        # Carregar jogos
        QTimer.singleShot(100, self.load_games_from_api)

    def create_modern_header(self):
        """Header com busca em tempo real"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(26, 26, 26, 255),
                    stop:1 rgba(26, 26, 26, 0)
                );
                border: none;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(30, 20, 30, 20)
        
        logo = QLabel("🎮 GameStore")
        logo.setFont(QFont("Arial", 18, QFont.Bold))
        logo.setStyleSheet("color: #47D64E;")
        
        self.search_input.setPlaceholderText("🔍 Buscar jogos na Steam...")
        self.search_input.setFixedHeight(45)
        self.search_input.setFixedWidth(450)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(71, 214, 78, 0.3);
                border-radius: 22px;
                padding: 10px 45px 10px 20px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.15);
                border-color: #47D64E;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        clear_btn = QPushButton("✕", self.search_input)
        clear_btn.setFixedSize(30, 30)
        clear_btn.move(410, 7)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                border-radius: 15px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        clear_btn.clicked.connect(self.clear_search)
        clear_btn.hide()
        self.clear_search_btn = clear_btn
        
        layout.addWidget(logo)
        layout.addStretch()
        layout.addWidget(self.search_input)
        
        return header
    
    def create_hero_banner(self):
        """Banner de destaque"""
        hero = QFrame()
        hero.setFixedHeight(350)
        hero.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a1a,
                    stop:1 #2a2a2a
                );
                border-radius: 12px;
                margin: 20px;
            }
        """)
        
        layout = QHBoxLayout(hero)
        layout.setContentsMargins(40, 40, 40, 40)
        
        info = QVBoxLayout()
        
        title = QLabel("Bem-vindo à GameStore")
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        subtitle = QLabel("Milhares de jogos ao seu alcance")
        subtitle.setFont(QFont("Arial", 16))
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        
        cta = QPushButton("🎮 Explorar Jogos")
        cta.setFixedSize(200, 50)
        cta.setCursor(Qt.PointingHandCursor)
        cta.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                color: #1F1F1F;
                border: none;
                border-radius: 25px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5ce36c,
                    stop:1 #47D64E
                );
            }
        """)
        cta.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        
        info.addWidget(title)
        info.addWidget(subtitle)
        info.addSpacing(20)
        info.addWidget(cta, alignment=Qt.AlignLeft)
        info.addStretch()
        
        layout.addLayout(info, 60)
        layout.addStretch(40)
        
        return hero
    
    def create_game_section(self, title, container):
        """Seção de jogos com scroll horizontal"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Título
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: white; padding-left: 5px;")
        layout.addWidget(title_label)
        
        # Scroll horizontal
        scroll = QScrollArea()
        scroll.setFixedHeight(280)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: #1a1a1a;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #47D64E;
                border-radius: 4px;
                min-width: 30px;
            }
        """)
        
        # Setup container
        cards_layout = QHBoxLayout(container)
        cards_layout.setContentsMargins(5, 5, 5, 5)
        cards_layout.setSpacing(15)
        cards_layout.setAlignment(Qt.AlignLeft)
        cards_layout.addStretch()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return section
    
    def create_game_card(self, game_name, game_id):
        card = QFrame()
        # Altura ajustada para acomodar nomes de até 2 linhas (255 -> 275)
        card.setFixedSize(180, 275)
        card.setCursor(Qt.PointingHandCursor)
        card.setProperty("spotlight", False)

        card.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 12px;
                border: 2px solid transparent;
            }
            QFrame:hover {
                background: #2a2a2a;
            }
            QFrame[spotlight="true"] {
                background: #222e1a;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        image = QLabel()
        image.setFixedSize(164, 200)
        image.setAlignment(Qt.AlignCenter)
        image.setStyleSheet("""
            QLabel {
                background: #181d14;
                border-radius: 8px;
                border: none;
            }
        """)
        self.load_game_poster(image, game_id)

        # Truncar nome muito longo e permitir quebra em até 2 linhas
        font = QFont("Arial", 10, QFont.Bold)
        name = QLabel()
        name.setFont(font)
        
        # Calcular largura disponível (card width - padding - margins)
        available_width = 164  # mesma largura da imagem
        
        # Verificar se precisa truncar
        metrics = QFontMetrics(font)
        elided_text = metrics.elidedText(game_name, Qt.ElideRight, available_width)
        
        # Se o texto foi truncado ou muito longo, usar elipsis
        if len(game_name) > 20:  # Nomes com mais de 20 caracteres
            # Tentar quebrar em 2 linhas primeiro
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            # Altura dinâmica para até 2 linhas
            name.setMinimumHeight(38)
            name.setMaximumHeight(55)  # Permite até 2 linhas
        else:
            # Nomes curtos, usar elided se necessário
            name.setText(elided_text)
            name.setWordWrap(False)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(38)
        
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 8px 4px 4px 4px;
                background: transparent;
                border-radius: 8px;
            }
        """)

        layout.addWidget(image)
        layout.addSpacing(3)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.on_game_card_clicked(game_id, game_name)
        return card

    def set_spotlight(self, enabled):
        self.setProperty("spotlight", enabled)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def load_game_poster(self, label, app_id):
        """Carrega poster otimizado para cards de jogos na home com cache"""
        # Placeholder otimizado
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 48px; color: #47D64E;")
        
        # Cache key única para este app_id
        cache_key = f"game_poster_{app_id}"
        
        # URLs otimizadas (menores primeiro para carregamento rápido)
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_hero.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
        ]
        
        def on_success(pixmap):
            try:
                if label and not label.isHidden() and not pixmap.isNull():
                    # Escalar apenas uma vez com tamanho final
                    scaled = pixmap.scaled(
                        164, 200,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    label.setPixmap(scaled)
            except (RuntimeError, AttributeError):
                pass
        
        def on_error():
            # Manter placeholder se falhar
            pass
        
        # Carregar com cache e tamanho máximo otimizado
        loader = ImageLoader(
            urls,
            cache_key=cache_key,
            max_size=(200, 250),  # Limitar tamanho para economizar memória
            parent_cache=self.image_cache
        )
        loader.signals.finished.connect(on_success)
        loader.signals.error.connect(on_error)
        
        self.thread_pool.start(loader)

    def on_game_card_clicked(self, game_id, game_name):
        """Abre tela de detalhes do jogo"""
        loading_dialog = self.create_loading_dialog(game_name)
        loading_dialog.show()
        
        worker = DetailsWorker(game_id, self.api_url_site)
        
        def on_success(details):
            loading_dialog.close()
            
            # Remover tela de detalhes anterior se existir
            if hasattr(self, 'tela_detalhes') and self.tela_detalhes:
                try:
                    self.pages.removeWidget(self.tela_detalhes)
                    self.tela_detalhes.deleteLater()
                except:
                    pass
            
            # Criar nova tela de detalhes
            self.tela_detalhes = GameDetailsScreen(self, game_id, details)
            
            # Adicionar ao stack e trocar para ela
            details_index = self.pages.addWidget(self.tela_detalhes)
            self.pages.setCurrentIndex(details_index)
        
        def on_error(error_msg):
            loading_dialog.close()
            QMessageBox.warning(self, "Erro", f"Não foi possível carregar detalhes:\n{error_msg}")
        
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        
        self.thread_pool.start(worker)

    def create_loading_dialog(self, game_name):
        """Dialog de loading animado"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setFixedSize(400, 200)
        dialog.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel(f"Carregando {game_name}...")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        
        spinner = QLabel("⏳")
        spinner.setFont(QFont("Arial", 48))
        spinner.setAlignment(Qt.AlignCenter)
        spinner.setStyleSheet("color: #47D64E;")
        
        # Animação
        def animate():
            current = spinner.text()
            spinner.setText("⌛" if current == "⏳" else "⏳")
        
        timer = QTimer(dialog)
        timer.timeout.connect(animate)
        timer.start(500)
        
        layout.addWidget(spinner)
        layout.addWidget(title)
        
        return dialog

    def start_download_from_api(self, game_id, game_name):
        """Inicia download direto da API generator.ryuu.lol com DownloadProgressOverlay"""

        # Verificar Steam
        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro",
                "Steam não encontrada!\n\n"
                "Por favor, instale o Steam Client primeiro.")
            return

        # URL de download
        download_url = f"https://generator.ryuu.lol/secure_download?appid={game_id}&auth_code=RYUUMANIFESTtsl1c9"

        try:
            log_message(f"[START_DOWNLOAD] Iniciando download - game_id={game_id}, game_name={game_name}")
            
            # Criar dialog de progresso
            progress_dialog = DownloadProgressOverlay(self, game_name)
            
            # Criar worker
            worker = DownloadWorker(game_id, download_url, game_name, steam_path)
            progress_dialog.worker = worker  # Guardar referência
            
            # Conectar signals
            worker.signals.progress.connect(progress_dialog.progress_bar.set_value)
            worker.signals.status.connect(progress_dialog.status_label.setText)
            worker.signals.speed.connect(progress_dialog.progress_bar.set_speed)
            worker.signals.downloaded.connect(progress_dialog.progress_bar.set_downloaded)
            worker.signals.success.connect(progress_dialog.on_download_success)
            worker.signals.error.connect(progress_dialog.on_download_error)
            
            # Iniciar download
            self.thread_pool.start(worker)
            
            # Mostrar dialog (modal)
            result = progress_dialog.exec_()
            
            # Se o download foi concluído com sucesso (result == QDialog.Accepted)
            if result == QDialog.Accepted:
                # Após dialog fechar, perguntar sobre reiniciar Steam
                QTimer.singleShot(500, lambda: self.ask_restart_steam())
                
                # Trocar para tela de jogos após um pequeno delay
                QTimer.singleShot(1000, lambda: self.pages.setCurrentIndex(1))  # tela_jogos
                
                # Recarregar lista de jogos instalados
                QTimer.singleShot(1200, self.load_installed_games)
            
            log_message("[START_DOWNLOAD] Download concluído")
            
        except Exception as e:
            log_message(f"[START_DOWNLOAD] ERRO ao iniciar download: {e}", include_traceback=True)
            import traceback
            traceback.print_exc()
            try:
                QMessageBox.critical(self, "Erro", f"Erro ao iniciar download:\n{str(e)}")
            except Exception as e2:
                log_message(f"[START_DOWNLOAD] ERRO ao mostrar QMessageBox: {e2}")
    
    def on_download_finished(self, message, game_id):
        """Callback quando download termina"""
        log_message(f"[START_DOWNLOAD] Download finalizado - tela permanece aberta")
        # Não voltar automaticamente - deixar usuário escolher quando voltar

    def on_download_success(self, message, filepath, game_id):
        """Callback de sucesso do download"""
        QMessageBox.information(self, "✅ Sucesso", message)

    def on_download_error(self, error_msg):
        """Callback de erro do download"""
        QMessageBox.critical(self, "❌ Erro", f"Falha no download:\n\n{error_msg}")

    def on_download_progress(self, progress):
        """Callback de progresso"""
        # TODO: Atualizar dialog de progresso
        print(f"[PROGRESS] {progress}%")

    def on_download_status(self, status):
        """Callback de status"""
        # TODO: Atualizar texto do dialog de progresso
        print(f"[STATUS] {status}")

    # ========================================================================
    # SEÇÃO 3: SISTEMA DE BUSCA
    # ========================================================================
    
    def on_search_complete(self, results):
        """Processa resultados de forma minimalista"""
        while self.search_cards_layout.count():
            item = self.search_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not results:
            self.search_results_title.setText("Nenhum resultado encontrado")
            
            empty = QLabel("😔\n\nNenhum jogo encontrado com esse nome\nTente outro termo de busca")
            empty.setAlignment(Qt.AlignCenter)
            empty.setFont(QFont("Arial", 14))
            empty.setStyleSheet("color: rgba(255, 255, 255, 0.5); padding: 50px;")
            
            self.search_cards_layout.addWidget(empty, 0, 0, 1, 6)
            return
        
        query = self.search_input.text().strip()
        self.search_results_title.setText(f"🔍 Resultados para \"{query}\" ({len(results)} encontrados)")
        max_results = 18  # 3 linhas de 6
        for i, game in enumerate(results[:max_results]):
            row = i // 4
            col = i % 4
            
            card = self.create_netflix_search_card(game['nome'], str(game['appid']))
            self.search_cards_layout.addWidget(card, row, col)
        
        # Se tiver mais resultados
        if len(results) > max_results:
            more_text = QLabel(f"+ {len(results) - max_results} jogos adicionais")
            more_text.setAlignment(Qt.AlignCenter)
            more_text.setFont(QFont("Arial", 12))
            more_text.setStyleSheet("color: rgba(255, 255, 255, 0.5); padding: 20px;")
            
            self.search_cards_layout.addWidget(more_text, (max_results // 6) + 1, 0, 1, 6)

    def create_netflix_search_card(self, game_name, game_id):
        card = QFrame()
        # Altura ajustada para acomodar nomes de até 2 linhas (250 -> 270)
        card.setFixedSize(180, 270)
        card.setCursor(Qt.PointingHandCursor)
        card.setProperty("spotlight", False)
        card.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 12px;
                border: 2px solid transparent;
            }
            QFrame:hover {
                background: #2a2a2a;
            }
            QFrame[spotlight="true"] {
                background: #222f1a;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)   # Espaço para a borda respirar
        layout.setSpacing(0)
        
        poster = QLabel()
        poster.setFixedSize(164, 192)
        poster.setAlignment(Qt.AlignCenter)
        poster.setStyleSheet("""
            QLabel {
                background: #191d14;
                border-radius: 7px;
                border: none;
            }
        """)
        self.load_search_poster_safe(poster, game_id)
        
        # Truncar nome muito longo e permitir quebra em até 2 linhas
        font = QFont("Arial", 10, QFont.Bold)
        name = QLabel()
        name.setFont(font)
        
        # Calcular largura disponível
        available_width = 164
        
        # Verificar se precisa truncar
        metrics = QFontMetrics(font)
        
        # Se o texto foi truncado ou muito longo, usar quebra de linha
        if len(game_name) > 20:  # Nomes com mais de 20 caracteres
            # Tentar quebrar em 2 linhas primeiro
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            # Altura dinâmica para até 2 linhas
            name.setMinimumHeight(38)
            name.setMaximumHeight(55)  # Permite até 2 linhas
        else:
            # Nomes curtos, usar elided se necessário
            elided_text = metrics.elidedText(game_name, Qt.ElideRight, available_width)
            name.setText(elided_text)
            name.setWordWrap(False)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(38)
        
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 8px 4px 4px 4px;
                background: transparent;
                border-radius: 6px;
            }
        """)
        
        layout.addWidget(poster)
        layout.addSpacing(6)
        layout.addWidget(name)
        
        card.mousePressEvent = lambda event: self.on_search_result_clicked(game_id, game_name)
        return card

    def load_search_poster_safe(self, label, app_id):
        """Carrega poster otimizado com cache e múltiplos fallbacks"""
        # Placeholder
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 48px; color: #47D64E;")
        
        # Cache key para busca
        cache_key = f"search_poster_{app_id}"
        
        # URLs otimizadas (prioridade para imagens menores)
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
        ]
        
        def safe_set_pixmap(pixmap, target_label):
            try:
                if target_label and not target_label.isHidden() and not pixmap.isNull():
                    # Escalar mantendo proporção
                    scaled = pixmap.scaled(
                        200, 180, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    target_label.setPixmap(scaled)
                    target_label.setStyleSheet("""
                        QLabel {
                            background: #1a1a1a;
                            border-top-left-radius: 8px;
                            border-top-right-radius: 8px;
                        }
                    """)
            except (RuntimeError, AttributeError):
                pass  # Label deletado
        
        # Carregar com cache e tamanho máximo
        loader = ImageLoader(
            urls,
            cache_key=cache_key,
            max_size=(250, 200),  # Tamanho máximo para economizar memória
            parent_cache=self.image_cache
        )
        loader.signals.finished.connect(lambda pixmap: safe_set_pixmap(pixmap, label))
        loader.signals.error.connect(lambda: None)  # Silencioso em erro
        
        self.thread_pool.start(loader)
    
    def create_search_result_item(self, game_name, game_id):
        """Cria item de resultado otimizado"""
        item = QFrame()
        item.setFixedHeight(70)
        item.setCursor(Qt.PointingHandCursor)
        item.setStyleSheet("""
            QFrame {
                background: transparent;
                border-radius: 8px;
                padding: 5px;
            }
            QFrame:hover {
                background: rgba(71, 214, 78, 0.15);
                border: 1px solid rgba(71, 214, 78, 0.3);
            }
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(15)
        
        thumb = QLabel()
        thumb.setFixedSize(120, 54)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                background: #1a1a1a;
                border-radius: 6px;
                border: 1px solid #333;
            }
        """)
        
        self.load_search_thumbnail(thumb, game_id)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        name_label = QLabel(game_name)
        name_label.setFont(QFont("Arial", 12, QFont.Bold))
        name_label.setStyleSheet("color: white;")
        name_label.setWordWrap(False)
        name_label.setMaximumWidth(700) 
        
        id_label = QLabel(f"🎮 Steam ID: {game_id}")
        id_label.setFont(QFont("Arial", 10))
        id_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        
        badge = QLabel("Steam Store")
        badge.setFont(QFont("Arial", 9))
        badge.setStyleSheet("""
            QLabel {
                background: rgba(71, 214, 78, 0.2);
                color: #47D64E;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)
        badge.setFixedWidth(80)
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(id_label)
        info_layout.addWidget(badge)
        info_layout.addStretch()
        
        arrow = QLabel("→")
        arrow.setFont(QFont("Arial", 20))
        arrow.setStyleSheet("color: rgba(71, 214, 78, 0.5);")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(30)
        
        layout.addWidget(thumb)
        layout.addLayout(info_layout, 1)
        layout.addWidget(arrow)
        
        item.mousePressEvent = lambda event: self.on_search_result_clicked(game_id, game_name)
        return item
    
    def show_search_loading(self):
        """Loading minimalista"""
        # Limpar
        while self.search_cards_layout.count():
            item = self.search_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.search_results_title.setText("🔍 Buscando...")
        
        loading = QLabel("⏳\n\nCarregando resultados...")
        loading.setAlignment(Qt.AlignCenter)
        loading.setFont(QFont("Arial", 14))
        loading.setStyleSheet("color: rgba(255, 255, 255, 0.6); padding: 50px;")
        
        self.search_cards_layout.addWidget(loading, 0, 0, 1, 6)
    
    def on_search_text_changed(self, text):
        """Callback quando texto muda"""
        if hasattr(self, 'clear_search_btn'):
            self.clear_search_btn.setVisible(len(text) > 0)
        
        if len(text) >= 3:
            self.search_timer.start()
            
            self.hero_banner.setVisible(False)
            self.games_scroll_area.setVisible(False)
            
            self.search_results_main_container.setVisible(True)
        else:
            self.search_timer.stop()
            
            self.hero_banner.setVisible(True)
            self.games_scroll_area.setVisible(True)
            self.search_results_main_container.setVisible(False)
    
    def perform_search(self):
        """Executa busca na API"""
        query = self.search_input.text().strip()
        
        if len(query) < 3:
            return
        
        self.show_search_loading()
        
        url = f"{self.api_url_site}/buscar-jogos-loja?q={query}"
        
        print(f"[SEARCH] Buscando: {query}")
        print(f"[SEARCH] URL: {url}")
        
        worker = SearchWorker(url)
        worker.signals.finished.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        
        self.thread_pool.start(worker)
    
    def load_search_thumbnail(self, label, app_id):
        """Carrega thumbnail com fallback"""
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 24px; color: #47D64E;")
        
        # URLs para tentar
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_184x69.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_184x69.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
        ]
        
        def on_success(pixmap):
            try:
                if label and not label.isHidden():
                    scaled = pixmap.scaled(120, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(scaled)
                    label.setStyleSheet("""
                        QLabel {
                            background: transparent;
                            border-radius: 6px;
                            border: 1px solid #333;
                        }
                    """)
            except RuntimeError:
                pass
        
        # Cache para thumbnails
        cache_key = f"thumb_{app_id}"
        loader = ImageLoader(
            urls,
            cache_key=cache_key,
            max_size=(150, 70),  # Thumbnail pequeno
            parent_cache=self.image_cache
        )
        loader.signals.finished.connect(on_success)
        loader.signals.error.connect(lambda: None)  # Silencioso
        
        self.thread_pool.start(loader)
    
    def on_search_result_clicked(self, game_id, game_name):
        """Ao clicar em card de busca"""
        self.on_game_card_clicked(game_id, game_name)
        
    def hide_search_results(self):
        """Oculta resultados"""
        while self.search_results_main_layout.count():
            item = self.search_results_main_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()
        
        self.search_results_main_container.setFixedHeight(0)
        
    def on_search_error(self, error_msg):
        """Trata erros de busca"""
        while self.search_results_main_layout.count():
            item = self.search_results_main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        error_label = QLabel(f"⚠️ Erro: {error_msg}")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: #ff4444; padding: 20px; font-size: 13px;")
        self.search_results_main_layout.addWidget(error_label)
        
        self.search_results_main_container.setFixedHeight(100)
    
    def clear_search(self):
        """Limpa busca"""
        self.search_input.clear()
        
        self.hero_banner.setVisible(True)
        self.games_scroll_area.setVisible(True)
        self.search_results_main_container.setVisible(False)
        
        self.search_input.setFocus()
    
    # ========================================================================
    # SEÇÃO 4: GERENCIAMENTO DE JOGOS
    # ========================================================================
    
    def load_games_from_api(self):
        """Carrega jogos da API com ordem aleatória"""
        try:
            print(f"API URL site: {self.api_url_site}")
            response = requests.get(f"{self.api_url_site}/jogos-publicos", timeout=10)
            data = response.json()
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                
                if jogos:
                    
                    import random
                    jogos_aleatorios = jogos.copy()
                    random.shuffle(jogos_aleatorios)
                    
                    self.populate_game_section(self.all_games_container, jogos_aleatorios)
                else:
                    self.show_empty_state()
                    
        except Exception as e:
            import traceback
            traceback.print_exc()

    def show_empty_state(self):
        """Mostra mensagem de lista vazia"""
        for container in [self.popular_container, self.recent_container, self.all_games_container]:
            layout = container.layout()
            if not layout:
                layout = QHBoxLayout(container)
            
            # Limpar
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Mensagem vazia
            empty_label = QLabel("📦 Nenhum jogo disponível")
            empty_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.5);
                    font-size: 16px;
                    padding: 40px;
                }
            """)
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)

    def load_sample_games(self):
        """Carrega jogos de exemplo (fallback)"""
        sample_games = [
            {'nome': 'Counter-Strike 2', 'appid': '730', 'id': 1},
            {'nome': 'Dota 2', 'appid': '570', 'id': 2},
            {'nome': 'Team Fortress 2', 'appid': '440', 'id': 3},
            {'nome': 'Left 4 Dead 2', 'appid': '550', 'id': 4},
            {'nome': 'Portal 2', 'appid': '620', 'id': 5},
            {'nome': 'Half-Life 2', 'appid': '220', 'id': 6},
            {'nome': 'GTA V', 'appid': '271590', 'id': 7},
            {'nome': 'The Witcher 3', 'appid': '292030', 'id': 8},
            {'nome': 'Cyberpunk 2077', 'appid': '1091500', 'id': 9},
            {'nome': 'Red Dead Redemption 2', 'appid': '1174180', 'id': 10},
            {'nome': 'Elden Ring', 'appid': '1245620', 'id': 11},
            {'nome': 'Hogwarts Legacy', 'appid': '990080', 'id': 12},
            {'nome': 'Baldur\'s Gate 3', 'appid': '1086940', 'id': 13},
            {'nome': 'Starfield', 'appid': '1716740', 'id': 14},
            {'nome': 'Spider-Man Remastered', 'appid': '1817070', 'id': 15},
        ]
        
        print(f"📦 Usando {len(sample_games)} jogos de exemplo")
        
        self.populate_game_section(self.popular_container, sample_games[:10])
        self.populate_game_section(self.recent_container, sample_games[5:15])
        self.populate_game_section(self.all_games_container, sample_games)
    
    def populate_game_section(self, container, games):
        """Popula seção com jogos"""
        layout = container.layout()
        if not layout:
            layout = QHBoxLayout(container)
        
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for game in games:
            card = self.create_game_card(game.get('nome', 'Sem nome'), str(game.get('appid', '0')))
            layout.addWidget(card)
        
        layout.addStretch()
    
    def start_download(self, game_id, game_name):
        """Inicia download do jogo"""
        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro", "Steam não encontrada!")
            return
        
        worker = DownloadWorker(game_id, None, game_name, steam_path)
        worker.signals.success.connect(lambda msg, path, id: self.on_download_success(msg))
        worker.signals.error.connect(self.on_download_error)
        
        self.thread_pool.start(worker)
    
    def on_download_success(self, message):
        """Download concluído"""
        QMessageBox.information(self, "Sucesso", message)
    
    def on_download_error(self, error):
        """Erro no download"""
        QMessageBox.critical(self, "Erro", f"Falha no download:\\n{error}")
    
    # ========================================================================
    # SEÇÃO 5: SETUP DE OUTRAS PÁGINAS
    # ========================================================================
    
    def setup_jogos(self):
        """Tela de jogos instalados com cards Netflix (largura fixa)"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(26, 26, 26, 255),
                    stop:1 rgba(26, 26, 26, 0)
                );
            }
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 20, 30, 20)
        
        title = QLabel("🎮 Meus Jogos Instalados")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        self.installed_count_label = QLabel("0 jogos instalados")
        self.installed_count_label.setFont(QFont("Arial", 12))
        self.installed_count_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        
        # NOVO: Botão de instalação manual
        btn_manual_install = QPushButton("📥 Instalar Manualmente")
        btn_manual_install.setFixedSize(200, 45)
        btn_manual_install.setCursor(Qt.PointingHandCursor)
        btn_manual_install.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                color: #1F1F1F;
                border: none;
                border-radius: 22px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5ce36c,
                    stop:1 #6ff57d
                );
            }
            QPushButton:pressed {
                background: #3cb043;
            }
        """)
        btn_manual_install.clicked.connect(self.open_manual_install_dialog)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.installed_count_label)
        header_layout.addSpacing(15)
        header_layout.addWidget(btn_manual_install)
        
        layout.addWidget(header)
        
        # Restante do código permanece igual...
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #1a1a1a;
            }
            QScrollBar::handle:vertical {
                background: #47D64E;
                border-radius: 4px;
            }
        """)
        
        container_wrapper = QWidget()
        wrapper_layout = QHBoxLayout(container_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addStretch()
        
        self.installed_games_container = QWidget()
        self.installed_games_container.setMaximumWidth(940)
        self.installed_games_layout = QGridLayout(self.installed_games_container)
        self.installed_games_layout.setContentsMargins(30, 20, 30, 20)
        self.installed_games_layout.setSpacing(20)
        self.installed_games_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        wrapper_layout.addWidget(self.installed_games_container)
        wrapper_layout.addStretch()
        
        scroll.setWidget(container_wrapper)
        layout.addWidget(scroll)
        
        self.tela_jogos.setLayout(layout)
        
        QTimer.singleShot(200, self.load_installed_games)

    def install_manual_game(self, filepath):
        """Instala jogo a partir de arquivo local"""
        try:
            # Verificar Steam
            if not self.steam_path:
                self.steam_path = self.get_steam_directory()
            
            if not self.steam_path:
                QMessageBox.critical(self, "Erro", 
                    "Steam não encontrada!\n\n"
                    "Por favor, instale o Steam Client primeiro.")
                return
            
            # Validar nome do arquivo
            filename = os.path.basename(filepath)
            match = re.match(r"^(.+?)\s*\((\d+)\)\.(zip|rar)$", filename, re.IGNORECASE)
            
            if not match:
                QMessageBox.critical(self, "Erro de Formato",
                    f"Nome de arquivo inválido!\n\n"
                    f"Esperado: Nome do Jogo (ID).zip ou .rar\n"
                    f"Recebido: {filename}")
                return
            
            game_name = match.group(1).strip()
            game_id = match.group(2)
            
            # Criar worker de instalação manual
            progress_dialog = ManualInstallProgressOverlay(
                self, game_id, game_name, filepath, self.steam_path
            )
            progress_dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao instalar jogo:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def open_manual_install_dialog(self, checked=False):
        """Abre tela de instalação manual de arquivo usando setCurrentIndex"""
        try:
            if self.manual_install_index is not None:
                self.pages.setCurrentIndex(self.manual_install_index)
            else:
                QMessageBox.warning(self, "Erro", "Tela de instalação manual não foi inicializada.")
        except Exception as e:
            log_message(f"[MANUAL_INSTALL] Erro ao abrir tela: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao abrir tela de instalação manual:\n{str(e)}")
        
    def load_installed_games(self):
        """Carrega jogos com grid 5 colunas"""
        try:
            registry_path = Path(os.getenv('APPDATA')) / "GamesStore" / "game_registry.json"
            
            if not registry_path.exists():
                self.show_no_games_installed()
                return
            
            with open(registry_path, 'r', encoding='utf-8') as f:
                games_data = json.load(f)
            
            if not games_data:
                self.show_no_games_installed()
                return
            
            while self.installed_games_layout.count():
                item = self.installed_games_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            count = len(games_data)
            self.installed_count_label.setText(f"{count} jogo{'s' if count != 1 else ''} instalado{'s' if count != 1 else ''}")
            
            for i, (game_name, game_info) in enumerate(games_data.items()):
                row = i // 4
                col = i % 4
                
                card = self.create_installed_game_card(game_name, game_info)
                self.installed_games_layout.addWidget(card, row, col)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.show_no_games_installed()

    def setup_dlcs(self):
        """Setup da página de DLCs"""
        layout = QVBoxLayout()
        
        label = QLabel("DLCs em breve!")
        label.setFont(QFont("Arial", 16, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(label)
        self.tela_dlcs.setLayout(layout)

    def create_installed_game_card(self, game_name, game_info):
        card = QFrame()
        card.setFixedSize(200, 270)
        card.setCursor(Qt.PointingHandCursor)
        card.setProperty("spotlight", False)
        card.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 14px;
                border: 2px solid transparent;
            }
            QFrame:hover {
                background: #2a2a2a;
            }
            QFrame[spotlight="true"] {
                background: #25391b;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        poster = QLabel()
        poster.setFixedSize(180, 210)
        poster.setAlignment(Qt.AlignCenter)
        poster.setStyleSheet("""
            QLabel {
                background: #131a12;
                border-radius: 10px;
                border: none;
            }
        """)
        game_id = game_info.get('id', '')
        self.load_search_poster_safe(poster, game_id)
        
        # Badge "Instalado" (opcional)
        badge = QLabel("✔ Instalado", poster)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFont(QFont("Segoe UI", 9, QFont.Bold))

        badge.setStyleSheet("""
            QLabel {
                background-color: rgba(46, 204, 113, 0.95);
                color: #0f2414;
                border-radius: 8px;
                padding: 4px 10px;
                min-width: 70px;
            }
        """)

        badge.adjustSize()
        badge.move(8, 8)
        
        # Truncar nome muito longo e permitir quebra em até 2 linhas
        from PyQt5.QtGui import QFontMetrics
        
        font = QFont("Arial", 11, QFont.Bold)
        name = QLabel()
        name.setFont(font)
        
        # Calcular largura disponível (card é maior aqui)
        available_width = 180
        
        # Verificar se precisa truncar
        metrics = QFontMetrics(font)
        
        # Se o texto foi truncado ou muito longo, usar quebra de linha
        if len(game_name) > 25:  # Nomes com mais de 25 caracteres
            # Tentar quebrar em 2 linhas primeiro
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            # Altura dinâmica para até 2 linhas
            name.setMinimumHeight(40)
            name.setMaximumHeight(60)  # Permite até 2 linhas
        else:
            # Nomes curtos, usar elided se necessário
            elided_text = metrics.elidedText(game_name, Qt.ElideRight, available_width)
            name.setText(elided_text)
            name.setWordWrap(False)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(40)
        
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 8px 6px 4px 6px;
                background: transparent;
                border-radius: 8px;
            }
        """)
        
        layout.addWidget(poster)
        layout.addSpacing(7)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.open_installed_game_modal(game_name, game_info)
        return card

    def show_no_games_installed(self):
        """Mostra estado vazio quando não há jogos"""
        # Limpar layout
        while self.installed_games_layout.count():
            item = self.installed_games_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Atualizar contador
        self.installed_count_label.setText("0 jogos instalados")
        
        # Mensagem vazia
        empty = QFrame()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignCenter)
        
        icon = QLabel("📦")
        icon.setFont(QFont("Arial", 80))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("color: rgba(255, 255, 255, 0.2);")
        
        text = QLabel("Nenhum jogo instalado")
        text.setFont(QFont("Arial", 18, QFont.Bold))
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        
        subtext = QLabel("Baixe jogos na aba Home para começar")
        subtext.setFont(QFont("Arial", 13))
        subtext.setAlignment(Qt.AlignCenter)
        subtext.setStyleSheet("color: rgba(255, 255, 255, 0.3);")
        
        empty_layout.addWidget(icon)
        empty_layout.addWidget(text)
        empty_layout.addWidget(subtext)
        
        self.installed_games_layout.addWidget(empty, 0, 0, 1, 5)

    def open_installed_game_modal(self, game_name, game_info):
        """Abre tela de gerenciamento do jogo instalado"""
        try:
            # Remover tela anterior se existir
            if self.tela_installed_game:
                try:
                    self.pages.removeWidget(self.tela_installed_game)
                    self.tela_installed_game.deleteLater()
                except:
                    pass
            
            # Criar nova tela de jogo instalado
            self.tela_installed_game = InstalledGameScreen(self, game_name, game_info)
            
            # Adicionar ao stack e trocar para ela
            installed_index = self.pages.addWidget(self.tela_installed_game)
            self.pages.setCurrentIndex(installed_index)
            
        except Exception as e:
            log_message(f"[INSTALLED_GAME] Erro ao abrir tela: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao abrir tela do jogo:\n{str(e)}")
        
    # ========================================================================
    # SEÇÃO 6: LÓGICA STEAM
    # ========================================================================
    
    def get_steam_directory(self):
        """Detecta diretório da Steam usando função utilitária"""
        steam_path = get_steam_directory()
        if steam_path:
            self.steam_path = steam_path.replace("/", "\\")
        return self.steam_path
    
    def get_installed_game_card_widget_by_id(self, game_id):
        for i in range(self.installed_games_layout.count()):
            item = self.installed_games_layout.itemAt(i)
            card = item.widget()
            # Ajuste para garantir card tem game_id
            if getattr(card, 'game_id', None) == game_id:
                return card
        return None

    def restart_steam(self):
        """Reinicia a Steam sem abrir CMD visível"""
        log_message("[RESTART_STEAM] Iniciando restart_steam")
        
        try:
            # Obter PID do próprio processo para evitar encerrá-lo
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)
            current_name = current_process.name().lower() if hasattr(current_process, 'name') else ''
            log_message(f"[RESTART_STEAM] PID atual: {current_pid}, nome: {current_name}")
            
            steam_process_names = ["steam.exe", "steamwebhelper.exe", "steamservice.exe", "gameoverlayui.exe"]
            processes_killed = 0
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # Evitar encerrar o próprio processo
                    if proc.info['pid'] == current_pid:
                        log_message(f"[RESTART_STEAM] Pulando próprio processo PID={current_pid}")
                        continue
                        
                    proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                    
                    # Verificar se é um processo Steam
                    if any(steam_name in proc_name for steam_name in steam_process_names):
                        log_message(f"[RESTART_STEAM] Encerrando processo Steam: {proc_name} (PID={proc.info['pid']})")
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            proc_obj.terminate()
                            # Aguardar um pouco antes de forçar kill
                            try:
                                proc_obj.wait(timeout=3)
                                processes_killed += 1
                            except psutil.TimeoutExpired:
                                proc_obj.kill()
                                processes_killed += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            log_message(f"[RESTART_STEAM] Erro ao encerrar processo {proc_name}: {e}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    log_message(f"[RESTART_STEAM] Erro ao iterar processos: {e}")
            
            log_message(f"[RESTART_STEAM] {processes_killed} processos Steam encerrados. Agendando abertura...")
            QTimer.singleShot(1800, self.open_steam_url)
        except Exception as e:
            log_message(f"[RESTART_STEAM] ERRO crítico em restart_steam: {e}", include_traceback=True)

    def open_steam_url(self):
        """Abre a Steam usando URL scheme"""
        log_message("[OPEN_STEAM] Iniciando open_steam_url")
        
        try:
            # Detectar se está rodando como .exe
            is_frozen = getattr(sys, 'frozen', False)
            log_message(f"[OPEN_STEAM] Modo frozen (exe): {is_frozen}")
            
            if is_frozen:
                # Quando executado como .exe, usar subprocess com flags adequadas
                # DETACHED_PROCESS previne que o processo filho encerre o pai
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                
                log_message("[OPEN_STEAM] Usando subprocess com flags DETACHED_PROCESS")
                # Usar cmd /c para executar o comando de forma isolada
                proc = subprocess.Popen(
                    ['cmd', '/c', 'start', '', 'steam://open/main'],
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True
                )
                log_message(f"[OPEN_STEAM] Processo iniciado com PID={proc.pid}")
            else:
                log_message("[OPEN_STEAM] Modo desenvolvimento, usando os.startfile")
                # Em desenvolvimento, usar os.startfile normalmente
                os.startfile("steam://open/main")
                log_message("[OPEN_STEAM] os.startfile executado")
        except (AttributeError, OSError) as e:
            log_message(f"[OPEN_STEAM] Erro AttributeError/OSError: {e}, tentando fallback Linux/Mac")
            # Fallback para Linux/Mac
            try:
                subprocess.Popen(
                    ['xdg-open', 'steam://open/main'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
                log_message("[OPEN_STEAM] Fallback xdg-open executado")
            except Exception as e2:
                log_message(f"[OPEN_STEAM] ERRO no fallback: {e2}")
        except Exception as e:
            log_message(f"[OPEN_STEAM] ERRO crítico: {e}", include_traceback=True)
            
    def ask_restart_steam(self):
        """Pergunta se deseja reiniciar a Steam de forma segura"""
        log_message("[RESTART] Iniciando ask_restart_steam")
        
        try:
            # Verificar se a janela ainda está visível antes de mostrar QMessageBox
            is_visible = self.isVisible()
            is_enabled = self.isEnabled()
            log_message(f"[RESTART] Janela visível={is_visible}, habilitada={is_enabled}")
            
            if not is_visible or not is_enabled:
                log_message("[RESTART] Janela não está visível ou habilitada, cancelando")
                return
            
            log_message("[RESTART] Mostrando QMessageBox.question...")
            reply = QMessageBox.question(
                self,
                "Reiniciar Steam",
                "O novo jogo foi instalado!\nDeseja reiniciar a Steam para aparecer na biblioteca?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            log_message(f"[RESTART] Resposta recebida: {reply}, Yes={QMessageBox.Yes}")
            
            if reply == QMessageBox.Yes:
                log_message("[RESTART] Usuário escolheu sim, agendando restart_steam")
                # Usar QTimer para garantir que está na thread principal
                QTimer.singleShot(100, self.restart_steam)
            else:
                log_message("[RESTART] Usuário escolheu não")
        except Exception as e:
            log_message(f"[RESTART] ERRO ao perguntar sobre reiniciar Steam: {e}", include_traceback=True)
            # Não fazer nada em caso de erro, apenas logar
            
    # ========================================================================
    # SEÇÃO 7: DRAG & DROP
    # ========================================================================
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.selected_file_path = path
            print(f"Arquivo selecionado: {path}")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
    
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
    
    def mouseReleaseEvent(self, event):
        self.old_pos = None

def start_software():
    window = GameApp()
    window.show()
    return window

if __name__ == "__main__":
    print("❌ Acesso negado. Execute pelo login.")