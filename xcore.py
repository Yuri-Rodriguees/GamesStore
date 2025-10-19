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
from PyQt5.QtCore import (Qt, QUrl, QSize, QMimeData, QPoint, QPropertyAnimation, QEasingCurve, 
                          QTimer, pyqtSignal, QThread, QRect, QRectF, pyqtProperty, QEventLoop, 
                          QObject, QRunnable, QThreadPool, QPointF, pyqtSlot as Slot)
from PyQt5.QtGui import (QFont, QIcon, QDesktopServices, QDragEnterEvent, QDropEvent, QColor, 
                         QPalette, QPen, QLinearGradient, QPainter, QPainterPath, QPixmap)
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QFrame, QStackedWidget, QListWidget, 
                             QFileDialog, QMessageBox, QGraphicsBlurEffect, QGraphicsColorizeEffect, 
                             QGraphicsOpacityEffect, QProgressBar, QGraphicsDropShadowEffect)

# Configurações
try:
    from config import SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE
    print("[INFO] Configurações carregadas de config.py")
except ImportError:
    print("[INFO] config.py não encontrado, usando variáveis de ambiente")
    
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    if isinstance(SECRET_KEY, str):
        SECRET_KEY = SECRET_KEY.encode()
    
    API_URL = os.getenv('API_URL', '')
    API_URL_SITE = os.getenv('API_URL_SITE', '')
    AUTH_CODE = os.getenv('AUTH_CODE', '')

if getattr(sys, 'frozen', False):
    if not all([SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE]):
        print("[ERRO] Configurações não encontradas no executável!")

def get_safe_download_dir():
    """Retorna diretório temporário do sistema"""
    try:
        temp_base = Path(tempfile.gettempdir()) / "GameStore_Temp"
        temp_base.mkdir(parents=True, exist_ok=True)
        
        test_file = temp_base / ".test"
        test_file.touch()
        test_file.unlink()
        
        return temp_base
    except Exception as e:
        log_message(f"Erro ao usar temp: {e}")
        script_dir = Path(__file__).parent / "temp_downloads"
        script_dir.mkdir(parents=True, exist_ok=True)
        return script_dir

def log_message(message):
    """Registra mensagens no arquivo de log"""
    try:
        log_path = Path(__file__).parent / 'log.txt'
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[LOG] {message}")

class DownloadWorkerSignals(QObject):
    """Sinais para comunicação do worker de download"""
    progress = pyqtSignal(int)  # Porcentagem (0-100)
    speed = pyqtSignal(float)   # Velocidade em MB/s
    downloaded = pyqtSignal(int, int)  # (baixado_MB, total_MB)
    status = pyqtSignal(str)  # Texto de status (Baixando/Extraindo/Instalando)
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
                log_message(f"Nome do jogo (Steam API): {game_name}")
                return game_name
            else:
                return f'jogo_{appid}'
                
        except Exception as e:
            log_message(f"Erro ao buscar Steam API (usando fallback): {e}")
            return f'jogo_{appid}'
    
    @Slot()
    def run(self):
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
            
            log_message(f"Iniciando download: {self.game_name} (ID: {self.game_id})")
            self.signals.status.emit(f"Baixando {self.game_name}...")
            
            headers = {
                'Connection': 'keep-alive',
                'Accept-Encoding': 'gzip, deflate',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(
                self.download_url, 
                headers=headers, 
                stream=True, 
                allow_redirects=True, 
                timeout=30
            )
            response.raise_for_status()
            
            # Detectar tipo de arquivo
            content_type = response.headers.get('content-type', '').lower()
            content_disposition = response.headers.get('content-disposition', '').lower()
            
            if 'zip' in content_type or 'zip' in content_disposition:
                extension = '.zip'
            elif 'rar' in content_type or 'rar' in content_disposition or 'x-rar' in content_type:
                extension = '.rar'
            else:
                total_size = int(response.headers.get('content-length', 0))
                extension = '.rar' if total_size > 100 * 1024 * 1024 else '.zip'
            
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', self.game_name)
            
            download_dir = get_safe_download_dir()
            
            filename = f"{safe_name} ({self.game_id}){extension}"
            filepath = download_dir / filename
            
            log_message(f"Salvando em: {filepath}")
            
            if filepath.exists():
                try:
                    filepath.unlink()
                except PermissionError:
                    timestamp = int(time.time())
                    filename = f"{safe_name} ({self.game_id})_{timestamp}{extension}"
                    filepath = download_dir / filename
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            
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
            log_message(f"Download concluído em {elapsed:.2f}s ({avg_speed_mbps:.2f} MB/s): {filepath}")
            
            # FASE 2: EXTRAÇÃO E INSTALAÇÃO (se steam_path fornecido)
            if self.steam_path:
                self.signals.status.emit("Extraindo arquivos...")
                self.signals.progress.emit(0)
                
                # Criar diretório temporário
                temp_base = Path(tempfile.gettempdir()) / "GameStore_Extract"
                temp_base.mkdir(parents=True, exist_ok=True)
                temp_dir = temp_base / f"extract_{int(time.time())}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                log_message(f"Extraindo para: {temp_dir}")
                
                # Extrair baseado no formato
                if str(filepath).lower().endswith('.zip'):
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        total_files = len(zip_ref.namelist())
                        for i, file in enumerate(zip_ref.namelist()):
                            zip_ref.extract(file, temp_dir)
                            progress = int((i / total_files) * 100)
                            self.signals.progress.emit(progress)
                    log_message("Extração ZIP concluída")
                
                elif str(filepath).lower().endswith('.rar'):
                    # Buscar WinRAR
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
        
        # Buscar na estrutura de pastas
        for item in os.listdir(source_dir):
            match = re.match(r"^(.*?)\s*\((\d+)\)$", item)
            if match:
                game_name = match.group(1).strip()
                game_id = match.group(2)
                log_message(f"ID encontrado: {game_name} ({game_id})")
                break
        
        if not game_id:
            # Buscar em arquivos .lua/.st
            for root, _, files in os.walk(source_dir):
                for file in files:
                    if file.lower().endswith(('.lua', '.st')):
                        match = re.search(r'(\d{5,7})', file)
                        if match:
                            game_id = match.group(1)
                            game_name = self.game_name or 'jogo'
                            log_message(f"ID encontrado em arquivo: {file} -> {game_id}")
                            break
                if game_id:
                    break
        
        if not game_id:
            raise ValueError("Não foi possível identificar o jogo no arquivo")
        
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

class SearchThread(QThread):
    """Thread para buscar jogos na Steam Store API"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self._is_cancelled:
                return
            
            url = "https://store.steampowered.com/api/storesearch"
            params = {"term": self.query, "cc": "us", "l": "en"}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            if self._is_cancelled:
                return
            
            data = response.json()
            results = [
                {"name": item["name"], "id": item["id"]} 
                for item in data.get("items", [])
            ]
            
            self.finished.emit(results)
            
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))

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
            
class SpotlightOverlay(QWidget):
    def __init__(self, parent, target_widget):
        super().__init__(parent)
        self.target_widget = target_widget
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(parent.rect())

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.anim_in.setDuration(600)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(1.0)
        self.anim_in.start()

        QTimer.singleShot(2500, self.fade_out)

        self.show()
        self.raise_()

    def fade_out(self):
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.anim_out.setDuration(600)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.finished.connect(self.deleteLater)
        self.anim_out.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRect(QRectF(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height()))

        btn_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
        btn_local = self.mapFromGlobal(btn_pos)
        btn_rect = QRect(btn_local, self.target_widget.size()).adjusted(-10, -10, 10, 10)

        spotlight = QPainterPath()
        spotlight.addRoundedRect(QRectF(btn_rect), 12, 12)
        path = path.subtracted(spotlight)

        painter.setBrush(QColor(0, 0, 0, 220))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
        
class GameApp(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.secret_key = SECRET_KEY
        self.api_url = API_URL
        self.api_url_site = API_URL_SITE
        self.auth_code = AUTH_CODE
        
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(200, 200, 600, 400)
        self.setStyleSheet("background-color: #1a1a1a; color: white; border-radius: 10px;")
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        self.setWindowTitle(f"Games Store v{__version__}")
        
        self.search_thread = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self._perform_search)
            
        self.drag_label = None
        self.old_pos = None
        self.setAcceptDrops(True)
        self.drag_over = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 5, 15, 5)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_layout = QHBoxLayout()
        
        menu_layout = QVBoxLayout()
        menu_layout.setAlignment(Qt.AlignTop)
        
        self.btn_home = QPushButton("Home")
        self.btn_games = QPushButton("Jogos")
        self.btn_dlcs = QPushButton("DLC's (Em breve)")
        
        menu_buttons = [self.btn_home, self.btn_games, self.btn_dlcs]
        for btn in menu_buttons:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #222;
                    color: white;
                    padding: 10px;
                    font-size: 14px;
                    border-radius: 5px;
                    text-align: left;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #333;
                }
            """)
            btn.setMinimumHeight(40)
            btn.setFocusPolicy(Qt.NoFocus)
            menu_layout.addWidget(btn)
        
        self.pages = QStackedWidget()
        
        self.tela_home = QWidget()
        self.tela_jogos = QWidget()
        self.tela_dlcs = QWidget()
        
        self.pages.addWidget(self.tela_home)
        self.pages.addWidget(self.tela_jogos)
        self.pages.addWidget(self.tela_dlcs)
        
        self.setup_home()
        self.setup_jogos()
        self.setup_dlcs()
        self.setup_autocomplete()
        
        self.btn_home.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_games.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_dlcs.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        
        content_layout.addLayout(menu_layout, 1)
        content_layout.addWidget(self.pages, 3)
        
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)
        self.update_game_list()
        
        QTimer.singleShot(0, self.get_steam_directory)
    
    def setup_help_menu(self):
        """Adiciona menu de ajuda com opção de atualização (OPCIONAL)"""
        try:
            menubar = self.menuBar()
            help_menu = menubar.addMenu('Ajuda')
            
            check_update_action = help_menu.addAction('Verificar Atualizações')
            check_update_action.triggered.connect(self.check_for_updates_manually)
            
            about_action = help_menu.addAction('Sobre')
            about_action.triggered.connect(self.show_about)
            
        except Exception as e:
            print(f"Erro ao criar menu: {e}")
    
    def check_for_updates_manually(self):
        """Verifica atualizações manualmente (quando usuário clicar)"""
        try:
            updater.check_and_update(self, show_no_update_message=True)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao verificar atualizações:\n{str(e)}"
            )
    
    def show_about(self):
        """Mostra diálogo Sobre"""
        QMessageBox.about(
            self,
            "Sobre Games Store KEY",
            f"<h3>Games Store KEY</h3>"
            f"<p>Versão: <b>{__version__}</b></p>"
            f"<p>Sistema de gerenciamento de chaves de jogos</p>"
            f"<p>© 2025 Games Store</p>"
        )
        
    def start_search(self):
        self.search_timer.start()

    def _perform_search(self):
        query = self.search_input.text()
        if len(query) < 3:
            self.list_widget.hide()
            self.search_progress.hide()
            return

        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.wait()

        self.search_thread = SearchThread(query)
        self.search_thread.finished.connect(self.on_search_complete)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()
        
    def on_download_progress(self, value):
        """Atualiza progresso circular"""
        print(f"[DEBUG] Progresso: {value}%")  # Debug
        self.circular_progress.set_value(value)
        self.progress_label.setText(f"Baixando... {value}%")

    def on_download_speed(self, speed):
        """Atualiza velocidade"""
        print(f"[DEBUG] Velocidade: {speed:.2f} MB/s")  # Debug
        self.circular_progress.set_speed(speed)

    def on_download_size(self, downloaded, total):
        """Atualiza tamanhos"""
        print(f"[DEBUG] Tamanho: {downloaded}/{total} MB")  # Debug
        self.circular_progress.set_downloaded(downloaded, total)

    def on_download_success(self, message, filepath):
        """Download concluído com sucesso"""
        self.hide_progress_overlay()
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Download Concluído")
        msg_box.setText(message)
        msg_box.setInformativeText(f"Arquivo salvo em:\n{filepath}")
        
        open_folder_btn = msg_box.addButton("Abrir Pasta", QMessageBox.ActionRole)
        msg_box.addButton(QMessageBox.Ok)
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == open_folder_btn:
            folder_path = os.path.dirname(filepath)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def on_download_error(self, error_message):
        """Erro no download"""
        self.hide_progress_overlay()
        
        QMessageBox.critical(
            self,
            "Erro no Download",
            f"Falha ao baixar o jogo:\n\n{error_message}",
            QMessageBox.Ok
        )

    def start_download(self, game_id, game_name):
        """Inicia download, extração e instalação automáticos"""
        
        # Obter caminho da Steam
        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro", "Steam não encontrada!")
            return
        
        # Criar overlay
        if not hasattr(self, 'overlay'):
            self.create_progress_overlay()
        
        # Resetar valores
        self.circular_progress.set_value(0)
        self.circular_progress.set_speed(0)
        self.circular_progress.set_downloaded(0, 0)
        self.progress_label.setText(f"Baixando {game_name}...")
        
        # Mostrar overlay
        self.show_progress_overlay(f"Iniciando download de {game_name}...")
        
        # Criar worker COM steam_path
        worker = DownloadWorker(game_id, None, game_name, steam_path)
        
        # Conectar sinais
        worker.signals.progress.connect(self.on_download_progress)
        worker.signals.speed.connect(self.on_download_speed)
        worker.signals.downloaded.connect(self.on_download_size)
        worker.signals.status.connect(self.on_download_status)  # NOVO
        worker.signals.success.connect(self.on_download_install_success)  # ALTERADO
        worker.signals.error.connect(self.on_download_error)
        worker.signals.finished.connect(self.on_download_finished)
        
        # Executar
        QThreadPool.globalInstance().start(worker)
        
        print(f"[DEBUG] Download iniciado para {game_name} (ID: {game_id})")
    
    def on_download_status(self, status):
        """Atualiza status textual (Baixando/Extraindo/Instalando)"""
        print(f"[DEBUG] Status: {status}")
        self.progress_label.setText(status)
    
    def on_download_install_success(self, message, filepath, game_id):
        """Download, extração e instalação concluídos"""
        self.hide_progress_overlay()
        
        # Atualizar lista de jogos instalados
        self.update_game_list()
        
        # Mostrar mensagem de sucesso
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("🎮 Instalação Concluída")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2a2a2a;
                color: white;
            }
            QMessageBox QLabel {
                color: white;
                font-size: 13px;
            }
            QPushButton {
                background-color: #47D64E;
                color: #1F1F1F;
                border: none;
                padding: 8px 20px;
                font-size: 12px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5ce36c;
            }
        """)
        
        msg_box.exec_()
        
        # Animação em etapas
        self.animate_transition_to_games()
        
        log_message(f"Instalação concluída: {game_id}")

    def animate_transition_to_games(self):
        """Animação suave de transição para aba de jogos"""
        # Passo 1: Processar eventos
        QApplication.processEvents()
        
        # Passo 2: Mudar para aba de Jogos
        self.pages.setCurrentIndex(1)
        
        # Passo 3: Processar eventos novamente
        QApplication.processEvents()
        
        # Passo 4: Aguardar 300ms e fazer efeito visual no botão "Jogos"
        QTimer.singleShot(300, lambda: self.highlight_games_button())
        
        # Passo 5: Aguardar 800ms e mostrar spotlight no refresh
        QTimer.singleShot(800, lambda: self.show_spotlight_on_refresh())

    def highlight_games_button(self):
        """Destaca brevemente o botão de Jogos"""
        # Salvar estilo original
        original_style = self.btn_games.styleSheet()
        
        # Aplicar destaque temporário
        self.btn_games.setStyleSheet("""
            QPushButton {
                background-color: #47D64E;
                color: #1F1F1F;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
                text-align: left;
                border: 2px solid #5ce36c;
            }
        """)
        
        # Voltar ao estilo original após 500ms
        QTimer.singleShot(500, lambda: self.btn_games.setStyleSheet(original_style))

    def show_spotlight_on_refresh(self):
        """Mostra spotlight no botão refresh"""
        try:
            if hasattr(self, 'btn_refresh'):
                SpotlightOverlay(self, self.btn_refresh)
        except Exception as e:
            print(f"Erro ao mostrar spotlight: {e}")

    def on_download_finished(self):
        """Limpeza após download"""
        print("[DEBUG] Download finalizado")

    def update_game_list(self, checked=False):
        try:
            registry_path = self.get_registry_path()
            if not registry_path:
                raise Exception("Caminho do registro inválido")

            self.game_list.setUpdatesEnabled(False)
            self.game_list.clear()

            installed_games = []

            if os.path.exists(registry_path):
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                    for game_name, game_data in registry.items():
                        game_id = game_data.get("id", "")
                        installed_games.append((game_name, game_id))

            installed_games.sort(key=lambda x: x[0].lower())

            for game_name, game_id in installed_games:
                display_name = f"{game_name} ({game_id})"
                self.game_list.addItem(display_name)

            if self.game_list.count() == 0:
                self.game_list.addItem("Nenhum jogo instalado")

        except Exception as e:
            print(f"Erro ao atualizar lista de jogos: {str(e)}")
            QMessageBox.warning(self, "Erro", "Falha ao carregar lista de jogos instalados")
        finally:
            self.game_list.setUpdatesEnabled(True)
            self.game_list.repaint()

    def remove_game(self, checked=False):
        selected_items = self.game_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Aviso", "Nenhum jogo selecionado para remover!")
            return

        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro", "Steam não encontrada!")
            return

        registry_path = self.get_registry_path()
        if not registry_path:
            QMessageBox.critical(self, "Erro", "Caminho do registro não encontrado!")
            return

        registry = {}
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                registry = json.load(f)

        for item in selected_items:
            game_name, game_id = self.extract_game_info(item.text())
            if not game_id:
                QMessageBox.warning(self, "Formato Inválido", f"'{item.text()}' não segue o padrão esperado!")
                continue

            try:
                if game_name in registry:
                    game_data = registry[game_name]
                    actual_game_id = game_data.get("id", "")

                    if actual_game_id != game_id:
                        QMessageBox.warning(self, "Erro", f"ID do jogo não corresponde ao registro!")
                        continue

                    for file_type, files in game_data["paths"].items():
                        dir_path = os.path.join(steam_path, "config",
                                                "stplug-in" if file_type in ["lua", "st"] else
                                                "StatsExport" if file_type == "bin" else
                                                "depotcache")

                        for file in files:
                            file_path = os.path.join(dir_path, file)
                            if os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                except Exception as e:
                                    print(f"Erro ao remover {file_path}: {str(e)}")

                if game_name in registry:
                    del registry[game_name]
                    with open(registry_path, 'w') as f:
                        json.dump(registry, f, indent=4)

                self.game_list.takeItem(self.game_list.row(item))
                QMessageBox.information(self, "Sucesso", f"{game_name} removido com sucesso!\nReinicie sua Steam clicando no botão abaixo!")
                QApplication.processEvents()
                QTimer.singleShot(1000, lambda: SpotlightOverlay(self, self.btn_refresh))

            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao remover {game_name}:\n{str(e)}")

        self.update_game_list()
            
    def hide_progress_overlay(self):
        """Esconde o overlay de progresso"""
        if hasattr(self, 'overlay'):
            self.overlay.hide()
        
        if hasattr(self, 'blur_overlay'):
            self.blur_animation.setStartValue(10)
            self.blur_animation.setEndValue(0)
            self.blur_animation.finished.connect(lambda: self.blur_overlay.hide())
            self.blur_animation.start()
    
    def setup_blur_overlay(self):
        self.blur_overlay = QWidget(self)
        self.blur_overlay.setGeometry(0, 0, self.width(), self.height())
        self.blur_overlay.setStyleSheet("background-color: transparent;")
        self.blur_overlay.lower()
        
        self.blur_effect = QGraphicsBlurEffect()
        self.blur_effect.setBlurRadius(0)
        self.blur_overlay.setGraphicsEffect(self.blur_effect)
        
        self.blur_animation = QPropertyAnimation(self.blur_effect, b"blurRadius")
        self.blur_animation.setDuration(500)
        self.blur_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        self.blur_overlay.hide()
        
    def show_progress_overlay(self, message):
        if not hasattr(self, 'overlay'):
            self.create_progress_overlay()
        
        self.progress_label.setText(message)
        self.circular_progress.set_value(0)
        
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.blur_overlay.setGeometry(0, 0, self.width(), self.height())
        
        self.overlay.raise_()
        self.blur_overlay.raise_()
        self.overlay.show()
        self.blur_overlay.show()
        
        self.blur_animation.setStartValue(0)
        self.blur_animation.setEndValue(10)
        self.blur_animation.start()
        
    def create_progress_overlay(self):
        self.overlay = QWidget(self)
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        
        layout = QVBoxLayout(self.overlay)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        self.progress_label = QLabel("Baixando...")
        self.progress_label.setStyleSheet("""
            color: white; 
            font-size: 18px;
            font-weight: bold;
        """)
        
        self.circular_progress = CircularProgressBar()
        
        layout.addWidget(self.progress_label)
        layout.addWidget(self.circular_progress, 0, Qt.AlignCenter)
        
        self.setup_blur_overlay()
        self.overlay.hide()
     
    def update_progress_bar(self, value):
        if abs(value - self.circular_progress.value) > 2 or value == 100:
            self.circular_progress.set_value(value)

    def on_download_complete(self, success, installer_path):
        if success:
            self.progress_label.setText("Instalando WinRAR...")
            self.circular_progress.set_value(100)
            
            steam_path = self.get_steam_directory()
            if not steam_path:
                self.progress_label.setText("Erro: Diretório Steam não encontrado")
                QTimer.singleShot(3000, self.hide_progress_overlay)
                return
            
            try:
                process = subprocess.Popen([installer_path, '/S'])
                
                self.installation_check_timer = QTimer(self)
                self.installation_check_timer.timeout.connect(
                    lambda: self.check_winrar_installation(process, installer_path, steam_path))
                self.installation_check_timer.start(1000)
                
            except Exception as e:
                print(f"Erro na instalação: {str(e)}")
                self.progress_label.setText(f"Erro: {str(e)}")
                QTimer.singleShot(3000, self.hide_progress_overlay)
        else:
            self.hide_progress_overlay()
    
    def setup_home(self):
        layout = QVBoxLayout()
        lbl_home = QLabel("Bem-vindo ao Games Store!")
        lbl_home.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_home.setAlignment(Qt.AlignCenter)
        
        self.setup_search_widgets()
        layout.addWidget(lbl_home)
        layout.addLayout(self.search_layout)
        
        self.tela_home.setLayout(layout)
    
    def setup_search_widgets(self):
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar jogos...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background: #333;
                color: white;
                margin: 10px;
            }
        """)
        
        self.list_widget = QListWidget()
        self.list_widget.hide()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                margin: 10px;
                max-height: 150px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:hover {
                background: #444;
            }
        """)
        
        self.search_progress = QProgressBar()
        self.search_progress.hide()
        self.search_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 2px;
                text-align: center;
                margin: 10px;
            }
            QProgressBar::chunk {
                background-color: #05B8CC;
            }
        """)
        
        self.game_image_label = QLabel()
        self.game_image_label.setAlignment(Qt.AlignCenter)
        self.game_image_label.setFixedSize(300, 140)
        self.game_image_label.setStyleSheet("""
            QLabel {
                background: transparent;
                margin: 10px;
            }
        """)
        
        self.search_result_label = QLabel("")
        self.search_result_label.setAlignment(Qt.AlignCenter)
        self.search_result_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 12px;
                margin: 10px;
            }
        """)
        
        self.search_layout = QVBoxLayout()
        self.search_layout.addWidget(self.search_input)
        self.search_layout.addWidget(self.search_progress)
        self.search_layout.addWidget(self.list_widget)
        
        game_info_layout = QVBoxLayout()
        game_info_layout.setAlignment(Qt.AlignCenter)
        game_info_layout.addWidget(self.game_image_label)
        game_info_layout.addWidget(self.search_result_label)
        
        self.search_layout.addLayout(game_info_layout)
        self.search_layout.addStretch()
        
        self.game_image_label.mousePressEvent = self.on_image_clicked
        self.game_image_label.setCursor(Qt.PointingHandCursor)
    
    def setup_autocomplete(self):
        self.games = []
        self.search_thread = None
        
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.start_search)
        
        self.search_input.textChanged.connect(self.schedule_search)
        self.list_widget.itemClicked.connect(self.on_game_selected)
    
    def schedule_search(self, text):
        self.debounce_timer.stop()
        if len(text) >= 3:
            self.search_progress.show()
            self.debounce_timer.start(500)
    
    def start_search(self):
        self.search_timer.start()

    def _perform_search(self):
        query = self.search_input.text()
        if len(query) < 3:
            self.list_widget.hide()
            self.search_progress.hide()
            return

        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.wait()

        self.search_thread = SearchThread(query)
        self.search_thread.finished.connect(self.on_search_complete)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()
    
    def on_search_complete(self, results):
        self.games = results
        self.list_widget.clear()
        
        if results:
            for game in results:
                self.list_widget.addItem(game["name"])
            self.list_widget.show()
        else:
            self.list_widget.hide()
            self.search_result_label.setText("Nenhum jogo encontrado")
        
        self.search_progress.hide()
    
    def on_search_error(self, error_msg):
        self.list_widget.hide()
        self.search_result_label.setText(f"Erro na busca: {error_msg}")
        self.search_progress.hide()
    
    def on_image_clicked(self, event):
        """Clique na imagem do jogo inicia download direto"""
        if hasattr(self, 'selected_game_id') and hasattr(self, 'selected_game_name'):
            reply = QMessageBox.question(
                self,
                "Confirmar Download",
                f"Deseja baixar e instalar '{self.selected_game_name}'?\n\n"
                f"O jogo será automaticamente instalado na sua Steam.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.start_download(self.selected_game_id, self.selected_game_name)

    def on_game_selected(self, item):
        selected_name = item.text()
        for game in self.games:
            if game["name"] == selected_name:
                self.selected_game_id = game["id"]
                self.search_result_label.setText(f"{game['name']}\n(ID: {game['id']})")
                self.load_game_image(game['id'])
                break
        self.list_widget.hide()

    def handle_download_progress(self, progress):
        """
        Atualiza a interface com o progresso do download
        
        Args:
            progress: Porcentagem de conclusão (0-100)
        """
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(progress)
        
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(f"Baixando... {progress}%")

    def handle_download_error(self, error_message):
        """
        Chamado quando ocorre um erro no download
        
        Args:
            error_message: Descrição do erro
        """
        self.hide_progress_overlay()
        
        QMessageBox.critical(
            self,
            "Erro no Download",
            f"Falha ao baixar o jogo:\n\n{error_message}",
            QMessageBox.Ok
        )
        
        log_message(f"Erro no download: {error_message}")

    def cleanup_download(self):
        """
        Limpeza após finalização do download (sucesso ou erro)
        """
        # Remover referência ao worker
        if hasattr(self, 'current_worker'):
            delattr(self, 'current_worker')
        
        log_message("Download finalizado (cleanup)")

    def cancel_download(self):
        """
        Cancela o download em andamento (se houver)
        Nota: QRunnable não suporta cancelamento nativo facilmente
        """
        if hasattr(self, 'current_worker'):
            # Para implementar cancelamento real, você precisaria:
            # 1. Adicionar um flag no DownloadWorker
            # 2. Verificar o flag durante o loop de download
            # 3. Interromper quando flag = True
            
            self.hide_progress_overlay()
            log_message("Download cancelado pelo usuário")
            
    def on_game_selected(self, item):
        selected_name = item.text()
        for game in self.games:
            if game["name"] == selected_name:
                self.selected_game_id = game["id"]
                self.selected_game_name = game["name"]
                self.search_result_label.setText(f"{game['name']}\n(ID: {game['id']})")
                self.load_game_image(game['id'])
                break
        self.list_widget.hide()

    def load_game_image(self, app_id):
        self.game_image_label.setText("Carregando imagem...")
        QTimer.singleShot(0, lambda: self.fetch_game_image(app_id))

    def fetch_game_image(self, app_id):
        try:
            urls = [
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
                f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg"
            ]
            
            for url in urls:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(response.content):
                        self.game_image_label.setPixmap(
                            pixmap.scaled(
                                self.game_image_label.width(),
                                self.game_image_label.height(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                        )
                        self.game_image_label.mousePressEvent = self.on_image_clicked
                        self.game_image_label.setCursor(Qt.PointingHandCursor)
                        return
            
            self.game_image_label.setText("Imagem não disponível")
        except Exception as e:
            self.game_image_label.setText("Erro ao carregar imagem")
            print(f"Erro ao carregar imagem: {e}")

    def setup_jogos(self):
        layout = QVBoxLayout()
        
        lbl_jogos = QLabel("Lista de Jogos Disponíveis")
        lbl_jogos.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_jogos.setAlignment(Qt.AlignCenter)

        self.game_list = QListWidget()
        self.game_list.addItems([])
        self.game_list.setStyleSheet("background-color: #333; color: white; border-radius: 5px; padding: 5px;")

        self.btn_select_file = QPushButton("Arraste e solte um arquivo ZIP/RAR ou pasta aqui ou clique para selecionar")
        self.btn_select_file.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                padding: 15px;
                font-size: 14px;
                border-radius: 5px;
                border: 2px dashed #555;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        self.btn_select_file.setFocusPolicy(Qt.NoFocus)
        self.btn_select_file.clicked.connect(lambda: self.select_file_dialog())
        
        self.selected_file_label = QLabel("Nenhum arquivo selecionado")
        self.selected_file_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.selected_file_label.setAlignment(Qt.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Instalar")
        btn_remove = QPushButton("Remover")

        button_style = """
            QPushButton {
                background-color: #008000;
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #00A000;
            }
        """
        
        button_style_remover = """
            QPushButton {
                background-color: #484a49;
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #bbbfbc;
            }
        """
        
        btn_add.setStyleSheet(button_style)
        btn_add.setFocusPolicy(Qt.NoFocus)
        btn_add.clicked.connect(lambda: self.install_game())

        btn_remove.setStyleSheet(button_style_remover)
        btn_remove.setFocusPolicy(Qt.NoFocus)
        btn_remove.clicked.connect(lambda: self.remove_game())

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)

        lbl_info = QLabel("Peça para adicionar este jogo no nosso Discord.")
        lbl_info.setAlignment(Qt.AlignCenter)
        lbl_info.setStyleSheet("""
            background-color: #111;
            color: white;
            font-size: 12px;
            padding: 12px;
            border-radius: 5px;
            min-height: 30px;
        """)
        
        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(QIcon(":/imgs/refresh.svg"))        
        self.btn_refresh.setIconSize(QSize(24, 24))
        self.btn_refresh.setFixedSize(40, 40)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #222;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.btn_refresh.setFocusPolicy(Qt.NoFocus)
        self.btn_refresh.clicked.connect(lambda: self.restart_steam())
        
        gamelist_layout = QHBoxLayout()
        gamelist_layout.addWidget(self.btn_refresh)

        footer_layout = QVBoxLayout()
        footer_layout.setAlignment(Qt.AlignHCenter)

        self.btn_discord = QPushButton()
        self.btn_discord.setFixedSize(40, 40)
        self.btn_discord.setStyleSheet("border: none;")
        self.btn_discord.setFocusPolicy(Qt.NoFocus)
        self.btn_discord.setIcon(QIcon(":/imgs/dc.svg"))
        self.btn_discord.setIconSize(self.btn_discord.size())
        self.btn_discord.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://discord.com/invite/gamestore")))

        self.steam_path_label = QLineEdit()
        self.steam_path_label.setReadOnly(True)
        self.steam_path_label.setStyleSheet("""
            background-color: #333;
            color: white;
            padding: 5px;
            border-radius: 5px;
            border: none;
        """)

        footer_layout.addWidget(self.btn_discord, alignment=Qt.AlignHCenter)
        footer_layout.addWidget(self.steam_path_label)

        layout.addWidget(lbl_jogos)
        layout.addWidget(self.game_list)
        layout.addWidget(self.btn_select_file)
        layout.addWidget(self.selected_file_label)
        layout.addLayout(btn_layout)
        layout.addWidget(lbl_info)
        layout.addLayout(gamelist_layout)
        layout.addLayout(footer_layout)

        self.tela_jogos.setLayout(layout)
        
        self.selected_file_path = None
    
    def setup_dlcs(self):
        layout = QVBoxLayout()
        lbl_dlcs = QLabel("DLC's estarão disponíveis em breve!")
        lbl_dlcs.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_dlcs.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_dlcs)
        self.tela_dlcs.setLayout(layout)

    def select_file_dialog(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Selecionar arquivo ZIP/RAR ou pasta", 
            "", 
            "Arquivos compactados (*.zip *.rar);;Todos os arquivos (*)", 
            options=options
        )
        
        if file_path:
            self.handle_selected_file(file_path)

    def handle_selected_file(self, file_path):
        self.selected_file_path = file_path
        file_name = os.path.basename(file_path)
        self.selected_file_label.setText(f"Arquivo selecionado: {file_name}")
        self.selected_file_label.setStyleSheet("color: #4CAF50; font-size: 12px;")

    def _reset_file_selection(self, checked=False):
        self.selected_file_path = None
        self.selected_file_label.setText("Nenhum arquivo selecionado")
        self.selected_file_label.setStyleSheet("color: #FF0000; font-size: 12px;")
                
    def extract_game_info(self, folder_name):
        match = re.match(r"^(.*?)\s*\((\d+)\)$", folder_name)
        if match:
            return match.group(1).strip(), match.group(2)
        return None, None

    def process_game_files(self, source_dir, steam_path):
        game_id = None
        game_name = None
        
        for item in os.listdir(source_dir):
            name, id = self.extract_game_info(item)
            if id:
                game_name, game_id = name, id
                break
        
        if not game_id:
            for root, dirs, _ in os.walk(source_dir):
                for dir in dirs:
                    name, id = self.extract_game_info(dir)
                    if id:
                        game_name, game_id = name, id
                        break
                if game_id:
                    break
        
        if not game_id:
            raise ValueError("Formato inválido. Use: 'Nome do Jogo (ID)'")
        
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
        
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                if file.lower().endswith('.lua'):
                    dest_path = os.path.join(stplugin_dir, file)
                    self.safe_move_file(file_path, dest_path)
                    moved_files['lua'].append(file)
                    
                elif file.lower().endswith('.st'):
                    dest_path = os.path.join(stplugin_dir, file)
                    self.safe_move_file(file_path, dest_path)
                    moved_files['st'].append(file)
                    
                elif file.lower().endswith('.bin'):
                    dest_path = os.path.join(StatsExport_dir, file)
                    self.safe_move_file(file_path, dest_path)
                    moved_files['bin'].append(file)
                    
                elif file.lower().endswith('.manifest'):
                    dest_path = os.path.join(depotcache_dir, file)
                    self.safe_move_file(file_path, dest_path)
                    moved_files['manifests'].append(file)
        
        self.update_game_list()
        
        return game_id, game_name, moved_files

    def safe_move_file(self, src, dst):
        
        try:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Arquivo de origem não encontrado: {src}")
            
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            
            if os.path.exists(dst):
                try:
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                except Exception as e:
                    raise IOError(f"Falha ao limpar destino existente: {str(e)}")
            
            try:
                shutil.move(src, dst)
                return
            except:
                pass
            
            shutil.copy2(src, dst)
            
            if not os.path.exists(dst):
                raise IOError("Falha na verificação pós-cópia")
                
            try:
                os.remove(src)
            except:
                print(f"Aviso: não foi possível remover o original: {src}")
        
        except PermissionError as e:
            raise PermissionError(f"Permissão negada ao mover {src} → {dst}: {str(e)}")
        except shutil.Error as e:
            raise IOError(f"Erro ao mover arquivos: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado ao mover {src}: {str(e)}")
    
    def get_registry_path(self):
        appdata_path = os.getenv('APPDATA')  
        if not appdata_path:
            return None

        games_store_path = os.path.join(appdata_path, "GamesStore")
        os.makedirs(games_store_path, exist_ok=True)

        return os.path.join(games_store_path, "game_registry.json")

    def get_steam_directory(self, checked=False):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                steam_path = steam_path.replace("/", "\\")
                
                self.move_required_files(steam_path)
                
                self.steam_path_label.setText(steam_path)
                return steam_path
                
        except Exception as e:
            self.steam_path_label.setText("Steam não encontrada")
            return None

    def move_required_files(self, steam_path):
        try:
            required_files = [
                (".cef-dev-tools-size.vdf", ".cef-dev-tools-size.vdf"),
                ("hid.dll", "hid.dll")
            ]
            
            assets_dir = os.path.join(os.path.dirname(__file__), "config")
            
            for src_name, dest_name in required_files:
                src_path = os.path.join(assets_dir, src_name)
                dest_path = os.path.join(steam_path, dest_name)
                
                if not os.path.exists(src_path):
                    continue
                    
                if os.path.exists(dest_path):
                    continue
                    
                try:
                    shutil.copy2(src_path, dest_path)
                except Exception as e:
                    print(f"Erro ao copiar arquivo {src_path}: {str(e)}")
                    
        except Exception as e:
            print(f"Erro ao mover arquivos necessários: {str(e)}")

    def restart_steam(self, checked=False):
        steam_path = self.get_steam_directory()
        if steam_path:
            for process in psutil.process_iter(['pid', 'name']):
                if "steam.exe" in process.info['name'].lower():
                    os.system(f"taskkill /F /PID {process.info['pid']}")
            os.system(f'start "" "{os.path.join(steam_path, "steam.exe")}"')
            self.steam_path_label.setText(steam_path)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if os.path.isfile(path) and path.lower().endswith(('.zip', '.rar')) or os.path.isdir(path):
                    event.acceptProposedAction()
                    self.set_drag_drop_effect(True)

    def dragLeaveEvent(self, event):
        self.set_drag_drop_effect(False)

    def dropEvent(self, event: QDropEvent):
        self.set_drag_drop_effect(False) 
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if os.path.isfile(path) and path.lower().endswith(('.zip', '.rar')) or os.path.isdir(path):
                    self.handle_selected_file(path)

    def set_drag_drop_effect(self, active):
        self.drag_over = active
        
        if not hasattr(self, 'colorize_effect'):
            self.colorize_effect = QGraphicsColorizeEffect(self)
            self.colorize_effect.setColor(QColor(0, 0, 0)) 
            self.colorize_effect.setStrength(0.9)  
            self.setGraphicsEffect(self.colorize_effect)
        
        if active:
            self.colorize_effect.setStrength(0.9) 
        else:
            self.colorize_effect.setStrength(0.0)
        
        self.update()
        
    def create_drag_label(self):
        if not self.drag_label:
            self.drag_label = QLabel("Solte aqui para instalar o jogo", self)
            self.drag_label.setAlignment(Qt.AlignCenter)
            self.drag_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 24px;
                    font-weight: bold;
                    background-color: rgba(0, 0, 0, 150);
                    border: 4px dashed white;
                    border-radius: 10px;
                    padding: 40px;
                }
            """)
            self.drag_label.hide()
            self.drag_label.setFixedSize(self.size())
            self.drag_label.move(0, 0)

    def set_drag_drop_effect(self, active):
        self.drag_over = active
        
        if active:
            self.create_drag_label()
            self.drag_label.show()
            
            blur_intensity = 45
            animation_duration = 500
            
            if not hasattr(self, 'blur_effect'):
                self.blur_effect = QGraphicsBlurEffect()
                self.blur_effect.setBlurRadius(0)
                
                for child in self.findChildren(QWidget):
                    if child != self.drag_label and child != self.title_bar:
                        child.setGraphicsEffect(self.blur_effect)
                
                self.blur_animation = QPropertyAnimation(self.blur_effect, b"blurRadius")
                self.blur_animation.setDuration(animation_duration)
                self.blur_animation.setEasingCurve(QEasingCurve.OutCubic)
            
            self.drag_label.raise_()
            
            self.blur_animation.setStartValue(0)
            self.blur_animation.setEndValue(blur_intensity)
            self.blur_animation.start()
            
        else:
            if hasattr(self, 'blur_animation'):
                if self.blur_animation.state() == QPropertyAnimation.Running:
                    self.blur_animation.stop()
                
                self.blur_animation.setDirection(QPropertyAnimation.Backward)
                self.blur_animation.start()
                
            if self.drag_label:
                QTimer.singleShot(self.blur_animation.duration(), self.drag_label.hide)
                
            def remove_blur():
                if not self.drag_over and hasattr(self, 'blur_effect'):
                    for child in self.findChildren(QWidget):
                        child.setGraphicsEffect(None)
                    del self.blur_effect
                    
            QTimer.singleShot(self.blur_animation.duration(), remove_blur)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.drag_label:
            self.drag_label.setFixedSize(self.size())

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

    def find_winrar(self, checked=False):
        winrar_paths = [
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
            r"C:\Program Files\WinRAR\Rar.exe",
            r"C:\Program Files (x86)\WinRAR\Rar.exe"
        ]
        
        winrar_in_path = shutil.which("WinRAR.exe") or shutil.which("Rar.exe")
        
        for path in winrar_paths:
            if os.path.exists(path):
                return path
        
        if winrar_in_path:
            return winrar_in_path
        
        return None
    
    def install_winrar(self, checked=False):
        self.create_progress_overlay()
        winrar_url = "https://www.rarlab.com/rar/winrar-x64-711br.exe"
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "winrar_installer.exe")
        
        self.pending_rar_file = self.selected_file_path
        
        self.show_progress_overlay("Baixando WinRAR...")
        
        self.download_thread = DownloadThread(winrar_url, installer_path)
        self.download_thread.progress_updated.connect(lambda: self.update_progress_bar())
        self.download_thread.download_complete.connect(lambda: self.on_winrar_download_complete())
        self.download_thread.start()
                  
    def check_winrar_installation(self, process, installer_path, steam_path):
        if process.poll() is None:
            return
        
        self.installation_check_timer.stop()
        
        try:
            os.remove(installer_path)
        except Exception as e:
            print(f"Erro ao remover instalador: {str(e)}")
        
        if self.find_winrar():
            self.progress_label.setText("WinRAR instalado com sucesso!")
            
            if hasattr(self, 'pending_rar_file') and self.pending_rar_file:
                try:
                    winrar_path = self.find_winrar()
                    temp_dir = tempfile.mkdtemp()
                    
                    subprocess.run([
                        winrar_path,
                        'x',
                        '-ibck',
                        '-inul',
                        self.pending_rar_file,
                        temp_dir
                    ], check=True)
                    
                    game_id, game_name, moved_files = self.process_game_files(temp_dir, steam_path)
                    
                    if game_id:
                        self.register_installation(game_name, game_id, steam_path, moved_files)
                        self.update_game_list()
                    
                    QMessageBox.information(self, "Sucesso", "Jogo instalado com sucesso!")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self, "Erro", f"Falha ao extrair arquivo RAR:\n{str(e)}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Ocorreu um erro:\n{str(e)}")
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    del self.pending_rar_file
                    self._reset_file_selection()
        else:
            self.progress_label.setText("Falha na instalação do WinRAR")
        
        QTimer.singleShot(2000, self.hide_progress_overlay)
        
    def on_winrar_download_complete(self, success):
        if not success:
            self.hide_progress_overlay()
            QMessageBox.critical(self, "Erro", "Falha ao baixar o WinRAR")
            return
        
        installer_path = self.download_thread.filename
        
        self.progress_label.setText("Solicitando permissões de administrador...")
        self.circular_progress.set_value(100)
        
        try:
            if os.name == 'nt':
                result = ctypes.windll.shell32.ShellExecuteW(
                    None, 
                    "runas",
                    installer_path,
                    "/S",
                    None,
                    1
                )
                
                if result <= 32:
                    raise Exception(f"Falha ao solicitar elevação (código {result})")
                
                self.installation_check_timer = QTimer(self)
                self.installation_check_timer.timeout.connect(
                    lambda: self.check_winrar_installation(installer_path))
                self.installation_check_timer.start(1000)
                
            else:
                subprocess.run([installer_path, '/S'], check=True)
                self.finalize_winrar_installation(installer_path)
                
        except Exception as e:
            print(f"Erro na instalação: {str(e)}")
            self.progress_label.setText(f"Erro: {str(e)}")
            QTimer.singleShot(3000, self.hide_progress_overlay)

    def check_winrar_installation(self, installer_path):
        try:
            process_name = os.path.basename(installer_path).lower()
            
            for proc in psutil.process_iter(['name']):
                if proc.info['name'].lower() == process_name:
                    return
            
            self.installation_check_timer.stop()
            self.finalize_winrar_installation(installer_path)
            
        except Exception as e:
            print(f"Erro ao verificar instalação: {str(e)}")
            self.installation_check_timer.stop()
            self.progress_label.setText("Instalação concluída")
            QTimer.singleShot(2000, self.hide_progress_overlay)

    def finalize_winrar_installation(self, installer_path):
        try:
            os.remove(installer_path)
        except Exception as e:
            print(f"Erro ao remover instalador: {str(e)}")
        
        if self.find_winrar():
            self.progress_label.setText("WinRAR instalado com sucesso!")
            QMessageBox.information(self, "Sucesso", "WinRAR instalado com sucesso!")
            
            if hasattr(self, 'pending_rar_file') and self.pending_rar_file:
                self.selected_file_path = self.pending_rar_file
                del self.pending_rar_file
                self.install_game()
        else:
            self.progress_label.setText("Falha na instalação do WinRAR")
            QMessageBox.warning(self, "Aviso", "A instalação do WinRAR pode não ter sido concluída com sucesso.")
        
        self.hide_progress_overlay()
        
def start_software():
    window = GameApp()
    window.show()
    return window

if __name__ == "__main__":
    print("❌ Acesso negado. Execute pelo login.")