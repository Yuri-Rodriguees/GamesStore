import os
import sys
import tempfile
import requests
import subprocess
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox

# versão inicial software
GITHUB_REPO = "Yuri-Rodriguees/GamesStore"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def log(msg):
    print(f"[UPDATER] {msg}")

def is_frozen():
    """Verifica se está rodando como .exe compilado"""
    return getattr(sys, 'frozen', False)

def get_current_version():
    try:
        from version import __version__
        log(f"Versão atual: {__version__}")
        return __version__
    except:
        return "0.0.0"

def check_for_updates():
    """Verifica atualizações - IGNORA prereleases automaticamente"""
    log("=" * 60)
    log("VERIFICANDO ATUALIZAÇÕES (APENAS STABLE)")
    log("=" * 60)
    
    if not is_frozen():
        log("⚠️ Modo desenvolvimento - pulando verificação")
        return False, None, None, None
    
    try:
        # A API /releases/latest AUTOMATICAMENTE ignora prereleases
        log(f"Consultando: {GITHUB_API_URL}")
        response = requests.get(GITHUB_API_URL, timeout=10)
        
        if response.status_code != 200:
            log(f"ERRO: Status {response.status_code}")
            return False, None, None, None
        
        data = response.json()
        
        # Verificar se é prerelease (não deveria ser, mas por segurança)
        if data.get("prerelease", False):
            log("⚠️ API retornou prerelease - ignorando")
            return False, None, None, None
        
        latest_version = data.get("tag_name", "").replace("v", "")
        release_notes = data.get("body", "Melhorias gerais")
        
        # Buscar .exe
        download_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url")
                log(f"EXE encontrado: {asset.get('name')}")
                break
        
        if not download_url:
            log("ERRO: Nenhum .exe encontrado")
            return False, None, None, None
        
        # Comparar versões
        current_version = get_current_version()
        
        try:
            # Limpar sufixos (caso tenha -beta no current)
            current_clean = current_version.replace("-beta", "")
            latest_clean = latest_version.replace("-beta", "")
            
            current = tuple(map(int, current_clean.split(".")))
            latest = tuple(map(int, latest_clean.split(".")))
            
            has_update = latest > current
            
            if has_update:
                log(f"✅ ATUALIZAÇÃO STABLE DISPONÍVEL: {current_version} → {latest_version}")
            else:
                log(f"ℹ️ JÁ ESTÁ ATUALIZADO")
            
            log("=" * 60)
            return has_update, latest_version, download_url, release_notes
            
        except ValueError as e:
            log(f"ERRO ao comparar versões: {e}")
            return False, None, None, None
        
    except Exception as e:
        log(f"ERRO: {e}")
        return False, None, None, None

class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url
        self._is_running = True
    
    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            temp_file = os.path.join(tempfile.gettempdir(), "GamesStore_Update.exe")
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._is_running:
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            self.progress.emit(int((downloaded / total_size) * 100))
            
            self.finished.emit(temp_file)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        self._is_running = False

class ModernUpdateDialog(QDialog):
    def __init__(self, parent, latest_version, release_notes):
        super().__init__(parent)
        self.setWindowTitle("Atualização Disponível")
        self.setFixedSize(500, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self.setStyleSheet("""
            QDialog { background-color: #1F1F1F; }
            QLabel { color: #E0E0E0; }
            QLabel#title { font-size: 20px; font-weight: bold; color: #47D64E; }
            QLabel#version { font-size: 16px; color: #47D64E; }
            QPushButton {
                background-color: #47D64E;
                color: #1F1F1F;
                border: none;
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #5ce36c; }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("🔄 Nova Atualização Disponível")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        version_label = QLabel(f"Versão {latest_version}")
        version_label.setObjectName("version")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        notes = release_notes[:200] + "..." if len(release_notes) > 200 else release_notes
        notes_label = QLabel(notes)
        notes_label.setWordWrap(True)
        notes_label.setAlignment(Qt.AlignCenter)
        notes_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(notes_label)
        
        layout.addStretch()
        
        from PyQt5.QtWidgets import QPushButton
        update_btn = QPushButton("Atualizar Agora")
        update_btn.clicked.connect(self.accept)
        layout.addWidget(update_btn)
        
        self.setLayout(layout)

class ModernProgressDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Atualizando...")
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self.setStyleSheet("""
            QDialog { background-color: #1F1F1F; }
            QLabel { color: #E0E0E0; font-size: 14px; }
            QProgressBar {
                border: 2px solid #333;
                border-radius: 5px;
                background-color: #2A2A2A;
                text-align: center;
                color: #E0E0E0;
                font-weight: bold;
            }
            QProgressBar::chunk { background-color: #7bf841; border-radius: 3px; }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.status_label = QLabel("Baixando...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.status_label.setText(f"Baixando... {value}%" if value < 100 else "Instalando...")


def perform_update(parent, download_url):
    progress_dialog = ModernProgressDialog(parent)
    progress_dialog.show()
    
    downloader = UpdateDownloader(download_url)
    downloader.progress.connect(progress_dialog.update_progress)
    downloader.finished.connect(lambda f: QTimer.singleShot(1000, lambda: install_update(f, progress_dialog)))
    downloader.error.connect(lambda e: (progress_dialog.close(), QMessageBox.critical(parent, "Erro", e)))
    downloader.start()
    
    parent._updater_thread = downloader
    return downloader


def install_update(temp_file, progress_dialog):
    current_exe = sys.executable
    
    batch_script = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{temp_file}" "{current_exe}"
start "" "{current_exe}"
exit
"""
    
    batch_file = os.path.join(tempfile.gettempdir(), "update_installer.bat")
    with open(batch_file, 'w') as f:
        f.write(batch_script)
    
    progress_dialog.close()
    subprocess.Popen(batch_file, shell=True)
    sys.exit(0)


def check_and_update(parent, show_no_update_message=False):
    has_update, latest_version, download_url, release_notes = check_for_updates()
    
    if not has_update:
        if show_no_update_message:
            QMessageBox.information(
                parent,
                "Sem Atualizações",
                f"Você já está na versão mais recente.\nVersão: v{get_current_version()}"
            )
        return None
    
    dialog = ModernUpdateDialog(parent, latest_version, release_notes)
    dialog.exec_()
    
    return perform_update(parent, download_url)