import requests
import os
import sys
import subprocess
import tempfile
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

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
        log(f"Versão atual lida: {__version__}")
        return __version__
    except Exception as e:
        log(f"ERRO ao ler version.py: {e}")
        return "0.0.0"

def check_for_updates():
    """Verifica se há atualizações disponíveis no GitHub"""
    log("=" * 60)
    log("INICIANDO VERIFICAÇÃO DE ATUALIZAÇÕES")
    log("=" * 60)
    
    # Se não estiver rodando como .exe, pular verificação
    if not is_frozen():
        log("⚠️ Rodando em modo desenvolvimento (não é .exe)")
        log("⚠️ Pulando verificação de atualizações")
        log("=" * 60)
        return False, None, None, None
    
    try:
        log(f"Consultando API: {GITHUB_API_URL}")
        
        response = requests.get(GITHUB_API_URL, timeout=10)
        
        if response.status_code != 200:
            log(f"ERRO: Status {response.status_code}")
            return False, None, None, None
        
        data = response.json()
        log(f"JSON recebido com sucesso")
        
        latest_version = data.get("tag_name", "").replace("v", "")
        release_notes = data.get("body", "Melhorias gerais e correções de bugs")
        
        download_url = None
        for asset in data.get("assets", []):
            asset_name = asset.get("name", "")
            log(f"  Asset: {asset_name}")
            
            if asset_name.endswith(".exe"):
                download_url = asset.get("browser_download_url")
                break
        
        if not download_url:
            log("ERRO: Nenhum .exe encontrado")
            return False, None, None, None
        
        current_version = get_current_version()
        
        try:
            current = tuple(map(int, current_version.split(".")))
            latest = tuple(map(int, latest_version.split(".")))
            
            log(f"Comparando: {latest} > {current}")
            
            has_update = latest > current
            
            if has_update:
                log(f"✅ ATUALIZAÇÃO DISPONÍVEL: {current_version} → {latest_version}")
            else:
                log(f"ℹ️ JÁ ESTÁ ATUALIZADO")
            
            log("=" * 60)
            return has_update, latest_version, download_url, release_notes
            
        except ValueError as e:
            log(f"ERRO ao comparar versões: {e}")
            return False, None, None, None
        
    except Exception as e:
        log(f"ERRO INESPERADO: {e}")
        return False, None, None, None

class UpdateDownloader(QThread):
    """Thread para baixar a atualização em background"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url
        self._is_running = True
    
    def run(self):
        try:
            log(f"Iniciando download: {self.download_url}")
            
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            log(f"Tamanho: {total_size / 1024 / 1024:.2f} MB")
            
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "GamesStore_Update.exe")
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._is_running:
                        log("Download cancelado")
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress_percent = int((downloaded / total_size) * 100)
                            self.progress.emit(progress_percent)
            
            log(f"Download concluído: {temp_file}")
            self.finished.emit(temp_file)
            
        except Exception as e:
            log(f"ERRO no download: {e}")
            self.error.emit(f"Erro ao baixar: {str(e)}")
    
    def stop(self):
        self._is_running = False

class ModernUpdateDialog(QDialog):
    """Diálogo moderno de atualização"""
    
    def __init__(self, parent, latest_version, release_notes):
        super().__init__(parent)
        self.setWindowTitle("Atualização Disponível")
        self.setFixedSize(500, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1F1F1F;
            }
            QLabel {
                color: #E0E0E0;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: bold;
                color: #47D64E;
            }
            QLabel#version {
                font-size: 16px;
                color: #47D64E;
            }
            QLabel#notes {
                font-size: 12px;
                color: #AAAAAA;
            }
            QPushButton {
                background-color: #47D64E;
                color: #1F1F1F;
                border: none;
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5ce36c;
            }
            QPushButton:pressed {
                background-color: #40bf55;
            }
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
        
        notes_label = QLabel(release_notes[:200] + "..." if len(release_notes) > 200 else release_notes)
        notes_label.setObjectName("notes")
        notes_label.setWordWrap(True)
        notes_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(notes_label)
        
        layout.addStretch()
        
        info_label = QLabel("A atualização será instalada automaticamente.")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(info_label)
        
        from PyQt5.QtWidgets import QPushButton
        update_btn = QPushButton("Atualizar Agora")
        update_btn.clicked.connect(self.accept)
        layout.addWidget(update_btn)
        
        self.setLayout(layout)

class ModernProgressDialog(QDialog):
    """Diálogo moderno de progresso"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Atualizando...")
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1F1F1F;
            }
            QLabel {
                color: #E0E0E0;
                font-size: 14px;
            }
            QProgressBar {
                border: 2px solid #333;
                border-radius: 5px;
                background-color: #2A2A2A;
                text-align: center;
                color: #E0E0E0;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #7bf841;
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.status_label = QLabel("Baixando atualização...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
        if value < 100:
            self.status_label.setText(f"Baixando... {value}%")
        else:
            self.status_label.setText("Instalando atualização...")

def perform_update(parent, download_url):
    """Baixa e instala a atualização"""
    log("Iniciando processo de atualização")
    
    progress_dialog = ModernProgressDialog(parent)
    progress_dialog.show()
    
    downloader = UpdateDownloader(download_url)
    
    def on_progress(value):
        progress_dialog.update_progress(value)
    
    def on_finished(temp_file):
        log(f"Download finalizado: {temp_file}")
        QTimer.singleShot(1000, lambda: install_update(temp_file, progress_dialog))
    
    def on_error(error_msg):
        progress_dialog.close()
        log(f"ERRO: {error_msg}")
        QMessageBox.critical(parent, "Erro na Atualização", f"Não foi possível baixar:\n\n{error_msg}")
    
    downloader.progress.connect(on_progress)
    downloader.finished.connect(on_finished)
    downloader.error.connect(on_error)
    downloader.start()
    
    parent._updater_thread = downloader
    
    return downloader

def install_update(temp_file, progress_dialog):
    """Instala a atualização e reinicia"""
    log("Instalando atualização")
    
    current_exe = sys.executable
    log(f"EXE atual: {current_exe}")
    log(f"EXE novo: {temp_file}")
    
    batch_script = f"""
@echo off
timeout /t 2 /nobreak >nul
move /y "{temp_file}" "{current_exe}"
start "" "{current_exe}"
exit
"""
    
    batch_file = os.path.join(tempfile.gettempdir(), "update_installer.bat")
    
    with open(batch_file, 'w') as f:
        f.write(batch_script)
    
    log(f"Script criado: {batch_file}")
    log("Reiniciando aplicativo...")
    
    progress_dialog.close()
    subprocess.Popen(batch_file, shell=True)
    sys.exit(0)

def check_and_update(parent, show_no_update_message=False):
    """Função principal - Atualização obrigatória se disponível"""
    
    has_update, latest_version, download_url, release_notes = check_for_updates()
    
    if not has_update:
        if show_no_update_message:
            if not is_frozen():
                QMessageBox.information(
                    parent,
                    "Modo Desenvolvimento",
                    f"Rodando em modo desenvolvimento.\n"
                    f"Versão atual: v{get_current_version()}\n\n"
                    f"Compile o .exe para testar atualizações."
                )
            else:
                QMessageBox.information(
                    parent,
                    "Sem Atualizações",
                    f"Você já está usando a versão mais recente (v{get_current_version()})."
                )
        return None
    
    dialog = ModernUpdateDialog(parent, latest_version, release_notes)
    dialog.exec_()
    
    return perform_update(parent, download_url)