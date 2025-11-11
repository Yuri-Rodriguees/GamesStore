import os
import stat
import rc
import re
import sys
import json
import time
import shutil
import psutil
import ctypes
import winreg
import updater
import zipfile
import tempfile
import requests
import datetime
import subprocess
import urllib.request
from pathlib import Path
from version import __version__
from urllib.parse import urlparse

from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkReply

from PyQt5.QtCore import (
    Qt, QUrl, QSize, QMimeData, QPoint, QPropertyAnimation, QEasingCurve, 
    QTimer, pyqtSignal, QThread, QRect, QRectF, pyqtProperty, QEventLoop, 
    QObject, QRunnable, QThreadPool, QPointF, pyqtSlot as Slot
)

from PyQt5.QtGui import (
    QFont, QIcon, QDesktopServices, QDragEnterEvent, QDropEvent, QColor, 
    QPalette, QPen, QLinearGradient, QPainter, QPainterPath, QPixmap
)

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QFrame, QScrollArea, QStackedWidget, QListWidget, QFileDialog, 
    QMessageBox, QGraphicsBlurEffect, QGraphicsColorizeEffect, 
    QGraphicsOpacityEffect, QProgressBar, QGraphicsDropShadowEffect,
    QDialog,  
    QListWidgetItem,  
    QSizePolicy, 
    QCheckBox,
    QTextEdit,
    QComboBox,
    QSpinBox, 
    QSystemTrayIcon, 
    QMenu,  
    QAction,
    QGridLayout
)

try:
    from config import SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE
except ImportError:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    if isinstance(SECRET_KEY, str):
        SECRET_KEY = SECRET_KEY.encode()

    API_URL = os.getenv('API_URL', '')
    API_URL_SITE = os.getenv('API_URL_SITE', '')
    AUTH_CODE = os.getenv('AUTH_CODE', '')

if getattr(sys, 'frozen', False):
    if not all([SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE]):
        pass

def get_safe_download_dir():
    """Retorna diretório temporário seguro do sistema"""
    try:
        temp_base = Path(tempfile.gettempdir()) / "GameStore_Temp"
        temp_base.mkdir(parents=True, exist_ok=True)
        
        test_file = temp_base / ".test"
        test_file.touch()
        test_file.unlink()
        
        return temp_base
    except Exception as e:
        # log_message(f"Erro ao usar temp: {e}")
        script_dir = Path(__file__).parent / "temp_downloads"
        script_dir.mkdir(parents=True, exist_ok=True)
        return script_dir

def get_log_directory():
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
    except Exception as e:
        # Fallback para pasta temporária se falhar
        temp_dir = Path(tempfile.gettempdir()) / "GamesStoreLauncher" / "logs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

def resource_path(relative_path):
    """Retorna o caminho absoluto para recursos, funciona em dev e PyInstaller"""
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)

def log_message(message):
    """Registra mensagens no arquivo de log (compatível com .exe)"""
    try:
        if getattr(sys, 'frozen', False):
            log_dir = Path(os.getenv('APPDATA')) / "GamesStoreLauncher" / "logs"
        else:
            log_dir = Path(__file__).parent / "logs"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'log.txt'
        
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        # Fallback silencioso para evitar crash
        print(f"[LOG] {message}")

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
    finished = pyqtSignal()

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
        filepath = None
        temp_dir = None
        
        try:
            # FASE 1: DOWNLOAD
            self.signals.status.emit("Preparando download...")
            
            if not self.game_name:
                self.game_name = self.get_game_name_from_steam(self.game_id)
            
            if not self.download_url:
                if not API_URL or not AUTH_CODE:
                    raise Exception("Configuração de API não encontrada")
                
                self.download_url = f"{API_URL}?appid={self.game_id}&auth_code={AUTH_CODE}"
            
            # log_message(f"Iniciando download: {self.game_name} (ID: {self.game_id})")
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
                    log_message("Extração ZIP concluída")
                
                elif str(filepath).lower().endswith('.rar'):
                    winrar_paths = [
                        r"C:\Program Files\WinRAR\WinRAR.exe",
                        r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
                    ]
                    
                    winrar_path = None
                    for path in winrar_paths:
                        if os.path.exists(path):
                            winrar_path = path
                            break
                    
                    if not winrar_path:
                        raise Exception("WinRAR não encontrado")
                    
                    subprocess.run(
                        [winrar_path, 'x', '-ibck', '-inul', str(filepath), str(temp_dir)],
                        check=True,
                        timeout=300
                    )
                    log_message("Extração RAR concluída")
                
                self.signals.progress.emit(100)
                self.signals.status.emit("Instalando arquivos do jogo...")
                self.signals.progress.emit(0)
                
                extracted_game_id, extracted_game_name, moved_files = self.process_game_files(
                    str(temp_dir), 
                    self.steam_path
                )
                
                self.register_game(extracted_game_name, extracted_game_id, moved_files)
                self.signals.progress.emit(100)
                
                self.signals.success.emit(
                    f"{extracted_game_name} instalado com sucesso!\n"
                    f"Velocidade média: {avg_speed_mbps:.2f} MB/s\n"
                    f"Reinicie a Steam para ver o jogo.",
                    str(filepath),
                    extracted_game_id
                )
            else:
                self.signals.success.emit(
                    f"Download de '{self.game_name}' concluído!\n"
                    f"Velocidade média: {avg_speed_mbps:.2f} MB/s",
                    str(filepath),
                    self.game_id
                )
            
        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            # log_message(error_msg)
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
                
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        log_message("Arquivo temporário removido")
                    except:
                        pass
            except Exception as e:
                log_message(f"Erro na limpeza: {e}")
            
            self.signals.finished.emit()
    
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
            raise ValueError("Nenhum arquivo válido encontrado")
        
        log_message(f"Total de arquivos instalados: {total_moved}")
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
            
            log_message(f"Jogo registrado: {game_name} (ID: {game_id})")

        except Exception as e:
            log_message(f"Erro ao registrar jogo: {e}")

class DownloadThread(QThread):
    progress_updated = pyqtSignal(int)
    download_complete = pyqtSignal(bool)

    def __init__(self, url, filename):
        super().__init__()
        self.url = url
        self.filename = filename

    def run(self):
        try:
            urllib.request.urlretrieve(
                self.url,
                self.filename,
                reporthook=self.update_progress
            )
            self.download_complete.emit(True)
        except Exception as e:
            print(f"Erro no download: {str(e)}")
            self.download_complete.emit(False)

    def update_progress(self, block_num, block_size, total_size):
        if total_size > 0:
            progress = int((block_num * block_size * 100) / total_size)
            self.progress_updated.emit(progress)

class TitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: #222; padding: 5px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        self.setFixedHeight(40)

        title_layout = QHBoxLayout(self)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        
        self.lbl_title = QLabel("Games Store")
        self.lbl_title.setFont(QFont("Arial", 10))
        self.lbl_title.setStyleSheet("color: white;")
        self.lbl_title.setAlignment(Qt.AlignLeft)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet("background: none; color: white; font-size: 14px; border: none;")
        self.btn_close.clicked.connect(parent.close)
        self.btn_close.setFocusPolicy(Qt.NoFocus)
        
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.btn_close)
        
class CircularProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self._value = 0
        self._speed = 0.0
        self._downloaded = 0
        self._total = 0
        self.max_value = 100
        self.progress_width = 10
        self.progress_rounded_cap = True
        self.progress_color = QColor(75, 215, 100)
        self.text_color = QColor(255, 255, 255)
        self.font_percent = QFont("Arial", 14, QFont.Bold)
        self.font_speed = QFont("Arial", 9)
        
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(20)
        self.shadow_effect.setXOffset(0)
        self.shadow_effect.setYOffset(0)
        self.shadow_effect.setColor(QColor(75, 215, 100, 150))
        self.setGraphicsEffect(self.shadow_effect)
        
    @pyqtProperty(int)
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value != self._value:
            self._value = max(0, min(value, self.max_value))
            self.update()
    
    def set_value(self, value):
        """Define o progresso (0-100)"""
        self.value = value
    
    def set_speed(self, speed):
        """Define a velocidade em MB/s"""
        self._speed = speed
        self.update()
    
    def set_downloaded(self, downloaded, total):
        """Define bytes baixados e total"""
        self._downloaded = downloaded
        self._total = total
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        side = min(self.width(), self.height())
        rect = QRectF(0, 0, side, side)
        
        # Fundo
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawEllipse(rect)
        
        # Progresso
        pen = QPen(self.progress_color, self.progress_width)
        if self.progress_rounded_cap:
            pen.setCapStyle(Qt.RoundCap)
        
        painter.setPen(pen)
        start_angle = 90 * 16
        span_angle = -int(self._value * 3.6 * 16)

        margin = self.progress_width / 2
        arc_rect = QRectF(
            margin, margin,
            side - self.progress_width,
            side - self.progress_width
        )
        
        painter.drawArc(arc_rect, start_angle, span_angle)
        
        # Texto - Porcentagem
        painter.setFont(self.font_percent)
        painter.setPen(self.text_color)
        
        percent_rect = QRectF(0, side * 0.35, side, side * 0.2)
        painter.drawText(percent_rect, Qt.AlignCenter, f"{self._value}%")
        
        # Texto - Velocidade
        if self._speed > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(200, 200, 200))
            speed_rect = QRectF(0, side * 0.55, side, side * 0.15)
            painter.drawText(speed_rect, Qt.AlignCenter, f"{self._speed:.1f} MB/s")
        
        # Texto - Tamanho
        if self._total > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(180, 180, 180))
            size_rect = QRectF(0, side * 0.68, side, side * 0.15)
            painter.drawText(size_rect, Qt.AlignCenter, f"{self._downloaded}/{self._total} MB")

class DownloadProgressOverlay(QDialog):
    def __init__(self, parent, game_id, game_name, download_url, steam_path):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(320, 320)
        self.setStyleSheet("background: rgba(26,26,26,0.97); border-radius: 20px;")
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)

        label = QLabel(f"Baixando\n{game_name}")
        label.setAlignment(Qt.AlignCenter)
        label.setFont(QFont("Arial", 14, QFont.Bold))
        label.setStyleSheet("color: white;")
        layout.addWidget(label)

        self.progress = CircularProgressBar(self)
        layout.addStretch()
        layout.addWidget(self.progress, alignment=Qt.AlignCenter)
        layout.addStretch()

        self.status_label = QLabel("Preparando download…")
        self.status_label.setStyleSheet("color: #cfcfcf;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Inicia worker
        self.worker = DownloadWorker(game_id, download_url, game_name, steam_path)
        self.worker.signals.progress.connect(self.progress.set_value)
        self.worker.signals.speed.connect(self.progress.set_speed)
        self.worker.signals.downloaded.connect(self.progress.set_downloaded)
        self.worker.signals.status.connect(self.status_label.setText)
        self.worker.signals.success.connect(self.on_download_success)
        self.worker.signals.error.connect(self.on_download_error)
        parent.thread_pool.start(self.worker)

    def on_download_success(self, message, filepath, game_id):
        self.accept()
        self.parent().after_download_success(game_id)

    def on_download_error(self, error_msg):
        QMessageBox.critical(self, "Falha no download", error_msg)
        self.reject()
               
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
    """Worker para carregar imagens com múltiplos fallbacks"""
    def __init__(self, urls):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.signals = ImageLoaderSignals()
    
    @Slot()
    def run(self):
        """Tenta carregar de múltiplas URLs até conseguir"""
        for url in self.urls:
            try:
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(response.content):
                        self.signals.finished.emit(pixmap)
                        return
                    
            except:
                pass
        
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

class OverlayModal(QWidget):
    """Modal overlay que aparece por cima da tela principal"""
    closed = pyqtSignal()
    
    def __init__(self, parent, game_id, details):
        super().__init__(parent)
        self.game_id = game_id
        self.details = details
        self.parent_widget = parent
        
        # Configurar como overlay
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WA_StyledBackground)
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.background = QFrame(self)
        self.background.setGeometry(self.rect())
        self.background.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.8);
            }
        """)
        self.background.mousePressEvent = lambda e: self.close_modal()
        
        self.modal_widget = QFrame(self)
        self.modal_widget.setFixedSize(900, 700)
        self.modal_widget.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
                border-radius: 12px;
                border: none;
            }
        """)
        
        # Centralizar modal
        modal_x = (self.width() - 900) // 2
        modal_y = (self.height() - 700) // 2
        self.modal_widget.move(modal_x, modal_y)
        
        # Setup do conteúdo do modal
        self.setup_modal_content()
        
        # Inicialmente oculto
        self.hide()
    
    def setup_modal_content(self):
        """Monta o conteúdo do modal"""
        layout = QVBoxLayout(self.modal_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        details = self.details
        game_id = self.game_id
        
        # Header
        header = QFrame()
        header.setFixedHeight(250)
        header.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_image = QLabel()
        header_image.setFixedSize(900, 250)
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        
        if details.get('background') or details.get('header_image'):
            bg_url = details.get('background') or details.get('header_image')
            loader = ImageLoader(bg_url)
            loader.signals.finished.connect(
                lambda pixmap: header_image.setPixmap(
                    pixmap.scaled(900, 250, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
            )
            self.parent_widget.thread_pool.start(loader)
        
        header_layout.addWidget(header_image)
        
        overlay = QLabel(header)
        overlay.setGeometry(0, 0, 900, 250)
        overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 transparent,
                stop:1 rgba(26, 26, 26, 0.9)
            );
        """)
        
        # Botão fechar
        close_btn = QPushButton("✕", header)
        close_btn.setFixedSize(40, 40)
        close_btn.move(850, 10)
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
                background: rgba(255, 0, 0, 0.8);
            }
        """)
        close_btn.clicked.connect(self.close_modal)
        
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
            download_btn.clicked.connect(lambda: self.parent_widget.start_download_from_api(game_id, details.get('nome', 'Jogo')))
            download_btn.clicked.connect(self.close_modal)
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
    
    def show_modal(self):
        """Mostra o modal com animação"""
        self.show()
        self.raise_()
    
    def close_modal(self):
        """Fecha o modal"""
        self.hide()
        self.closed.emit()
    
    def resizeEvent(self, event):
        """Reposiciona modal ao redimensionar janela"""
        super().resizeEvent(event)
        self.background.setGeometry(self.rect())
        
        modal_x = (self.width() - 900) // 2
        modal_y = (self.height() - 700) // 2
        self.modal_widget.move(modal_x, modal_y)

class InstalledGameModal(QWidget):
    """Modal para gerenciar jogo instalado"""
    closed = pyqtSignal()
    
    def __init__(self, parent, game_name, game_info):
        super().__init__(parent)
        self.game_name = game_name
        self.game_info = game_info
        self.parent_widget = parent
        self.game_id = game_info.get('id', '')
        
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet("background: transparent;")
        
        # Background
        self.background = QFrame(self)
        self.background.setGeometry(0, 0, self.width(), self.height())
        self.background.setStyleSheet("QFrame { background: rgba(0, 0, 0, 0.8); }")
        self.background.mousePressEvent = lambda e: self.close_modal()
        
        # Modal widget
        self.modal_widget = QFrame(self)
        self.modal_widget.setFixedSize(800, 600)
        self.modal_widget.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
                border-radius: 12px;
                border: none;
            }
        """)
        
        self.center_modal()
        self.setup_content()
        self.hide()
    
    def center_modal(self):
        modal_x = (self.width() - 800) // 2
        modal_y = (self.height() - 600) // 2
        self.modal_widget.move(modal_x, modal_y)
    
    def setup_content(self):
        layout = QVBoxLayout(self.modal_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(200)
        header.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_image = QLabel()
        header_image.setFixedSize(800, 200)
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        
        # Carregar imagem
        if self.game_id:
            url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.game_id}/header.jpg"
            loader = ImageLoader(url)
            loader.signals.finished.connect(
                lambda pixmap: header_image.setPixmap(
                    pixmap.scaled(800, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
            )
            self.parent_widget.thread_pool.start(loader)
        
        header_layout.addWidget(header_image)
        
        # Botão fechar
        close_btn = QPushButton("✕", header)
        close_btn.setFixedSize(40, 40)
        close_btn.move(750, 10)
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
                background: rgba(255, 0, 0, 0.8);
            }
        """)
        close_btn.clicked.connect(self.close_modal)
        
        layout.addWidget(header)
        
        # Conteúdo
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)
        
        # Título
        title = QLabel(self.game_name)
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)
        
        # Status instalado
        status = QLabel("✅ Jogo Instalado")
        status.setFont(QFont("Arial", 14))
        status.setStyleSheet("color: #47D64E;")
        
        # Informações
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)
        
        id_label = QLabel(f"🎮 Steam ID: {self.game_id}")
        id_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        
        install_date = self.game_info.get('install_date', 'N/A')
        date_label = QLabel(f"📅 Instalado em: {install_date}")
        date_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        
        # Contagem de arquivos
        manifests_count = len(self.game_info.get('paths', {}).get('manifests', []))
        files_label = QLabel(f"📦 {manifests_count} manifesto{'s' if manifests_count != 1 else ''}")
        files_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        
        info_layout.addWidget(id_label)
        info_layout.addWidget(date_label)
        info_layout.addWidget(files_label)
        
        content_layout.addWidget(title)
        content_layout.addWidget(status)
        content_layout.addSpacing(10)
        content_layout.addLayout(info_layout)
        content_layout.addStretch()
        
        layout.addWidget(content, 1)
        
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
        
        # Botão Jogar
        play_btn = QPushButton("▶️ Jogar")
        play_btn.setFixedHeight(55)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setStyleSheet("""
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
        play_btn.clicked.connect(lambda: self.launch_game())
        
        # Botão Desinstalar
        uninstall_btn = QPushButton("🗑️ Desinstalar")
        uninstall_btn.setFixedHeight(55)
        uninstall_btn.setCursor(Qt.PointingHandCursor)
        uninstall_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 68, 68, 0.2);
                color: #ff4444;
                border: 2px solid rgba(255, 68, 68, 0.5);
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                padding: 0 30px;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.3);
                border-color: #ff4444;
            }
        """)
        uninstall_btn.clicked.connect(lambda: self.uninstall_game())
        
        footer_layout.addWidget(play_btn, 2)
        footer_layout.addWidget(uninstall_btn, 1)
        
        layout.addWidget(footer)
    
    def launch_game(self):
        """Lança o jogo via Steam"""
        try:
            steam_url = f"steam://rungameid/{self.game_id}"
            QDesktopServices.openUrl(QUrl(steam_url))
            print(f"[LAUNCH] Abrindo jogo: {self.game_name} (ID: {self.game_id})")
            self.close_modal()
        except Exception as e:
            print(f"[LAUNCH] Erro: {e}")
            QMessageBox.warning(self.parent_widget, "Erro", f"Não foi possível iniciar o jogo:\n{e}")
    
    def uninstall_game(self):
        """Desinstala o jogo (remove json e arquivos físicos)"""
        reply = QMessageBox.question(
            self.parent_widget,
            "Confirmar Desinstalação",
            f"Tem certeza que deseja desinstalar '{self.game_name}'?\n\nIsso removerá todos os arquivos do jogo.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                registry_path = Path(os.getenv('APPDATA')) / "GamesStore" / "game_registry.json"
                steam_path = self.parent_widget.steam_path  # precisa obter o caminho Steam configurado
                
                with open(registry_path, 'r', encoding='utf-8') as f:
                    games_data = json.load(f)
                
                # Remover arquivos vinculados
                if self.game_name in games_data:
                    file_paths = games_data[self.game_name].get("paths", {})
                    
                    dirs = {
                        "lua": os.path.join(steam_path, "config", "stplug-in"),
                        "st": os.path.join(steam_path, "config", "stplug-in"),
                        "bin": os.path.join(steam_path, "config", "stplug-in"),  # ajuste se precisar
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
                    
                    # Também tenta remover arquivos de StatsExport se for necessário:
                    stats_export_dir = os.path.join(steam_path, "config", "StatsExport")
                    # Adicione lógica similar se jogos usarem esse diretório
                    
                    # Remove do registro
                    del games_data[self.game_name]

                    with open(registry_path, 'w', encoding='utf-8') as f:
                        json.dump(games_data, f, indent=4, ensure_ascii=False)
                    
                    QMessageBox.information(
                        self.parent_widget, "Sucesso",
                        f"'{self.game_name}' foi desinstalado com sucesso!"
                    )
                    
                    self.close_modal()
            except Exception as e:
                print(f"[UNINSTALL] Erro: {e}")
                QMessageBox.critical(self.parent_widget, "Erro", f"Erro ao desinstalar:\n{e}")
    
    def show_modal(self):
        self.show()
        self.raise_()
    
    def close_modal(self):
        self.hide()
        self.closed.emit()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setGeometry(0, 0, self.parent_widget.width(), self.parent_widget.height())
        self.background.setGeometry(0, 0, self.width(), self.height())
        self.center_modal()
        
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
                winrar_paths = [
                    r"C:\Program Files\WinRAR\WinRAR.exe",
                    r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
                ]
                
                winrar_path = None
                for path in winrar_paths:
                    if os.path.exists(path):
                        winrar_path = path
                        break
                
                if not winrar_path:
                    raise Exception("WinRAR não encontrado. Instale o WinRAR para extrair arquivos .rar")
                
                subprocess.run(
                    [winrar_path, 'x', '-ibck', '-inul', str(self.filepath), str(temp_dir)],
                    check=True,
                    timeout=300
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
        
        log_message(f"Total de arquivos instalados: {total_moved}")
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
            
            log_message(f"Jogo registrado: {game_name} (ID: {game_id})")
            
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
        
        self.image_cache = {}
        
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
        
        # Thread pool para downloads
        self.thread_pool = QThreadPool()
        
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
        
        self.pages.addWidget(self.tela_home)
        self.pages.addWidget(self.tela_jogos)
        self.pages.addWidget(self.tela_dlcs)
        
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
        card.setFixedSize(180, 255)
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

        name = QLabel(game_name)
        name.setFont(QFont("Arial", 10, QFont.Bold))
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 10px 6px 6px 6px;
                background: transparent;
                border-radius: 8px;
            }
        """)
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setFixedHeight(38)

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
        """Carrega poster para cards de jogos na home"""
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 48px; color: #47D64E;")
        
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_hero.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
        ]
        
        def on_success(pixmap):
            try:
                if label and not label.isHidden():
                    scaled = pixmap.scaled(180, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    label.setPixmap(scaled)
            except RuntimeError:
                pass
        
        loader = ImageLoader(urls)
        loader.signals.finished.connect(on_success)
        loader.signals.error.connect(lambda: None)
        
        self.thread_pool.start(loader)

    def on_game_card_clicked(self, game_id, game_name):
        """Abre modal overlay ao invés de QDialog"""
        loading_dialog = self.create_loading_dialog(game_name)
        loading_dialog.show()
        
        worker = DetailsWorker(game_id, self.api_url_site)
        
        def on_success(details):
            loading_dialog.close()
            
            overlay = OverlayModal(self, game_id, details)
            overlay.show_modal()
        
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
        """Inicia download direto da API generator.ryuu.lol com visual progressivo"""

        # Verificar Steam
        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro",
                "Steam não encontrada!\n\n"
                "Por favor, instale o Steam Client primeiro.")
            return

        # URL de download
        download_url = f"https://generator.ryuu.lol/secure_download?appid={game_id}&auth_code=RYUUMANIFESTtsl1c9"

        # Abre overlay de progresso
        progress_dialog = DownloadProgressOverlay(self, game_id, game_name, download_url, steam_path)
        progress_dialog.exec_()

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
        card.setFixedSize(180, 250)
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
        
        name = QLabel(game_name[:25] + '...' if len(game_name) > 25 else game_name)
        name.setFont(QFont("Arial", 10, QFont.Bold))
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 10px 6px 8px 6px;
                background: transparent;
                border-radius: 6px;
            }
        """)
        name.setAlignment(Qt.AlignCenter)
        name.setFixedHeight(38)
        
        layout.addWidget(poster)
        layout.addSpacing(6)
        layout.addWidget(name)
        
        card.mousePressEvent = lambda event: self.on_search_result_clicked(game_id, game_name)
        return card

    def load_search_poster_safe(self, label, app_id):
        """Carrega poster com múltiplos fallbacks"""
        # Placeholder
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 48px; color: #47D64E;")
        
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_467x181.jpg",
        ]
        
        def safe_set_pixmap(pixmap, target_label):
            try:
                if target_label and not target_label.isHidden():
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
            except RuntimeError:
                pass  # Label deletado
        
        loader = ImageLoader(urls)
        loader.signals.finished.connect(lambda pixmap: safe_set_pixmap(pixmap, label))
        loader.signals.error.connect(lambda: print(f"[POSTER] ❌ Todas URLs falharam para {app_id}"))
        
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
        
        loader = ImageLoader(urls)
        loader.signals.finished.connect(on_success)
        loader.signals.error.connect(lambda: print(f"[THUMB] ❌ Falhou para {app_id}"))
        
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

    def open_manual_install_dialog(self):
        """Abre dialog para seleção e instalação manual de arquivo"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setFixedSize(550, 400)
        dialog.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 16px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Título
        title = QLabel("📥 Instalação Manual de Jogo")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        
        # Instruções
        instructions = QLabel(
            "Selecione um arquivo .ZIP ou .RAR no formato:\n"
            "Nome do Jogo (ID).zip\n\n"
            "Exemplo: GTA V (271590).rar"
        )
        instructions.setFont(QFont("Arial", 11))
        instructions.setStyleSheet("color: rgba(255, 255, 255, 0.7); padding: 10px;")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setWordWrap(True)
        
        # Frame de seleção de arquivo
        file_frame = QFrame()
        file_frame.setFixedHeight(100)
        file_frame.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 12px;
            }
        """)
        
        file_layout = QVBoxLayout(file_frame)
        file_layout.setAlignment(Qt.AlignCenter)
        
        file_label = QLabel("📁 Nenhum arquivo selecionado")
        file_label.setFont(QFont("Arial", 11))
        file_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        file_label.setAlignment(Qt.AlignCenter)
        file_label.setWordWrap(True)
        
        file_layout.addWidget(file_label)
        
        # Botão de seleção
        btn_select = QPushButton("🔍 Selecionar Arquivo")
        btn_select.setFixedHeight(45)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 2px solid #47D64E;
                border-radius: 22px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #333333;
                border-color: #5ce36c;
            }
        """)
        
        selected_file_path = [None]  # Usar lista para mutabilidade
        
        def select_file():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Selecionar Arquivo de Jogo",
                os.path.expanduser("~"),
                "Arquivos de Jogo (*.zip *.rar);;Todos os Arquivos (*.*)"
            )
            
            if file_path:
                selected_file_path[0] = file_path
                filename = os.path.basename(file_path)
                file_label.setText(f"✅ {filename}")
                file_label.setStyleSheet("color: #47D64E;")
                
                # Validar formato
                match = re.match(r"^(.+?)\s*\((\d+)\)\.(zip|rar)$", filename, re.IGNORECASE)
                if not match:
                    file_label.setText(f"⚠️ {filename}\n(Formato inválido)")
                    file_label.setStyleSheet("color: #ff9500;")
        
        btn_select.clicked.connect(select_file)
        
        # Botões de ação
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedSize(120, 45)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: 22px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #333;
            }
        """)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_install = QPushButton("🚀 Instalar")
        btn_install.setFixedSize(120, 45)
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
                border-radius: 22px;
                font-size: 13px;
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
        
        def start_manual_install():
            if not selected_file_path[0]:
                QMessageBox.warning(dialog, "Aviso", "Selecione um arquivo primeiro!")
                return
            
            dialog.accept()
            self.install_manual_game(selected_file_path[0])
        
        btn_install.clicked.connect(start_manual_install)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_cancel)
        buttons_layout.addWidget(btn_install)
        
        # Montagem do layout
        layout.addWidget(title)
        layout.addWidget(instructions)
        layout.addWidget(file_frame)
        layout.addWidget(btn_select)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        
        dialog.exec_()
        
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
        badge = QLabel("✅ Instalado", poster)
        badge.setGeometry(9, 9, 80, 22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFont(QFont("Arial", 9, QFont.Bold))
        badge.setStyleSheet("""
            QLabel {
                background: rgba(71, 214, 78, 0.90);
                color: #141b13;
                border-radius: 5px;
                padding: 2px 8px;
            }
        """)
        
        display_name = game_name[:30] + '...' if len(game_name) > 30 else game_name
        name = QLabel(display_name)
        name.setFont(QFont("Arial", 11, QFont.Bold))
        name.setStyleSheet("""
            QLabel {
                color: white;
                padding: 10px 8px 6px 8px;
                background: transparent;
                border-radius: 8px;
            }
        """)
        name.setAlignment(Qt.AlignCenter)
        name.setFixedHeight(40)
        
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
        """Abre modal de gerenciamento do jogo instalado"""
        overlay = InstalledGameModal(self, game_name, game_info)
        overlay.closed.connect(self.load_installed_games)  # Recarregar ao fechar
        overlay.show_modal()
        
    # ========================================================================
    # SEÇÃO 6: LÓGICA STEAM
    # ========================================================================
    
    def get_steam_directory(self):
        """Detecta diretório da Steam"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Valve\\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                self.steam_path = steam_path.replace("/", "\\\\")
                return self.steam_path
        except:
            return None
    
    def after_download_success(self, game_id):
        # Troca a tela para jogos instalados e recarrega a lista
        self.pages.setCurrentWidget(self.tela_jogos)
        self.load_installed_games()
        
        # (Opcional) SpotlightOverlay para destacar o card recém-instalado
        card_widget = self.get_installed_game_card_widget_by_id(game_id)
        if card_widget:
            overlay = SpotlightOverlay(self, card_widget)
            overlay.show()
            QTimer.singleShot(2700, self.ask_restart_steam)
        else:
            # Se não quiser overlay ou não encontrar o card
            QTimer.singleShot(700, self.ask_restart_steam)

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
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'steam.exe' in proc.info['name'].lower():
                    proc.kill()
            except Exception:
                pass
        QTimer.singleShot(1800, self.open_steam_url)

    def open_steam_url(self):
        try:
            os.startfile("steam://open/main")
        except AttributeError:
            subprocess.Popen(['xdg-open', 'steam://open/main'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
    def ask_restart_steam(self):
        reply = QMessageBox.question(
            self,
            "Reiniciar Steam",
            "O novo jogo foi instalado!\nDeseja reiniciar a Steam para aparecer na biblioteca?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.restart_steam()
            
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