import os
import sys
import re
import tempfile
import time
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
    if "--test-update" in sys.argv:
        return True
    return getattr(sys, 'frozen', False)

def get_current_version():
    try:
        from version import __version__
        log(f"Versão atual: {__version__}")
        return __version__
    except:
        return "0.0.0"

def check_for_beta_updates():
    """Verifica atualizações BETA - para testar sistema de atualização"""
    log("=" * 60)
    log("VERIFICANDO ATUALIZAÇÕES BETA (PRERELEASES)")
    log("=" * 60)
    
    if not is_frozen():
        log("Modo desenvolvimento - pulando verificação")
        return False, None, None, None
    
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
        log(f"Consultando: {api_url}")
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            log(f"ERRO: Status {response.status_code}")
            return False, None, None, None
        
        releases = response.json()
        current_version = get_current_version()
        
        latest_beta = None
        latest_beta_version = None
        
        for release in releases:
            if not release.get("prerelease", False):
                continue
            
            tag_name = release.get("tag_name", "").replace("v", "")
            
            if "-old" in tag_name.lower():
                continue
            
            has_exe = False
            download_url = None
            for asset in release.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    has_exe = True
                    download_url = asset.get("browser_download_url")
                    break
            
            if not has_exe:
                continue
            
            try:
                current_clean = clean_version(current_version)
                latest_clean = clean_version(tag_name)
                
                current_parts = current_clean.split(".")
                latest_parts = latest_clean.split(".")
                
                while len(current_parts) < 3:
                    current_parts.append("0")
                while len(latest_parts) < 3:
                    latest_parts.append("0")
                
                current_tuple = tuple(map(int, current_parts[:3]))
                latest_tuple = tuple(map(int, latest_parts[:3]))
                
                if latest_tuple > current_tuple:
                    if latest_beta is None:
                        latest_beta = release
                        latest_beta_version = tag_name
                        log(f"Versão beta encontrada: {tag_name}")
                    else:
                        existing_clean = clean_version(latest_beta_version)
                        existing_parts = existing_clean.split(".")
                        while len(existing_parts) < 3:
                            existing_parts.append("0")
                        existing_tuple = tuple(map(int, existing_parts[:3]))
                        
                        if latest_tuple > existing_tuple:
                            latest_beta = release
                            latest_beta_version = tag_name
                            log(f"Versão beta mais recente encontrada: {tag_name}")
            except (ValueError, IndexError) as e:
                log(f"Erro ao comparar versão {tag_name}: {e}")
                continue
        
        if latest_beta is None:
            log("Nenhuma atualização beta disponível")
            log("=" * 60)
            return False, None, None, None
        
        download_url = None
        for asset in latest_beta.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url")
                log(f"EXE encontrado: {asset.get('name')}")
                break
        
        if not download_url:
            log("ERRO: Nenhum .exe encontrado na release beta")
            return False, None, None, None
        
        log(f"ATUALIZAÇÃO BETA DISPONÍVEL: {current_version} -> {latest_beta_version}")
        log("=" * 60)
        
        release_notes = latest_beta.get("body", "Melhorias gerais")
        return True, latest_beta_version, download_url, release_notes
        
    except Exception as e:
        log(f"ERRO: {e}")
        return False, None, None, None

def clean_version(version_str):
    """Remove prefixos e sufixos da versão, retornando apenas números"""
    if not version_str:
        return "0.0.0"
    
    try:
        numbers = re.findall(r'\d+', str(version_str))
        
        if len(numbers) >= 3:
            return f"{numbers[0]}.{numbers[1]}.{numbers[2]}"
        elif len(numbers) == 2:
            return f"{numbers[0]}.{numbers[1]}.0"
        elif len(numbers) == 1:
            return f"{numbers[0]}.0.0"
            
    except Exception as e:
        log(f"[clean_version] ERRO ao processar '{version_str}': {e}")
    
    return "0.0.0"

def check_for_updates():
    """Verifica atualizações - IGNORA prereleases automaticamente"""
    log("=" * 60)
    log("VERIFICANDO ATUALIZAÇÕES (APENAS STABLE)")
    log("=" * 60)
    
    if not is_frozen():
        log("Modo desenvolvimento - pulando verificação")
        return False, None, None, None
    
    try:
        log(f"Consultando: {GITHUB_API_URL}")
        response = requests.get(GITHUB_API_URL, timeout=10)
        
        if response.status_code != 200:
            log(f"ERRO: Status {response.status_code}")
            return False, None, None, None
        
        data = response.json()
        
        if data.get("prerelease", False):
            log("API retornou prerelease - ignorando")
            return False, None, None, None
        
        latest_version = data.get("tag_name", "").replace("v", "")
        release_notes = data.get("body", "Melhorias gerais")
        
        download_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url")
                log(f"EXE encontrado: {asset.get('name')}")
                break
        
        if not download_url:
            log("ERRO: Nenhum .exe encontrado")
            return False, None, None, None
        
        current_version = get_current_version()
        
        try:
            current_clean = clean_version(current_version)
            latest_clean = clean_version(latest_version)
            
            log(f"Versão atual: {current_clean}")
            log(f"Versão latest: {latest_clean}")
            
            current_parts = current_clean.split(".")
            latest_parts = latest_clean.split(".")
            
            while len(current_parts) < 3:
                current_parts.append("0")
            while len(latest_parts) < 3:
                latest_parts.append("0")
            
            for i, part in enumerate(current_parts[:3]):
                if not part.isdigit():
                    raise ValueError(f"Parte da versão não é número: '{part}'")
            
            for i, part in enumerate(latest_parts[:3]):
                if not part.isdigit():
                    raise ValueError(f"Parte da versão não é número: '{part}'")
            
            current = tuple(map(int, current_parts[:3]))
            latest = tuple(map(int, latest_parts[:3]))
            
            has_update = latest > current
            
            if has_update:
                log(f"ATUALIZAÇÃO DISPONÍVEL: {current_version} -> {latest_version}")
            else:
                log("JÁ ESTÁ ATUALIZADO")
            
            log("=" * 60)
            return has_update, latest_version, download_url, release_notes
            
        except (ValueError, IndexError) as e:
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
        
        title = QLabel("Nova Atualização Disponível")
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
    
    def on_download_finished(temp_file):
        try:
            QTimer.singleShot(1500, lambda: install_update(temp_file, progress_dialog))
        except Exception as e:
            log(f"ERRO no callback de download: {e}")
            progress_dialog.close()
            QMessageBox.critical(parent, "Erro", f"Erro ao processar download: {e}")
    
    def on_download_error(error_msg):
        try:
            progress_dialog.close()
            QMessageBox.critical(parent, "Erro no Download", f"Falha ao baixar atualização:\n\n{error_msg}")
        except Exception as e:
            log(f"ERRO ao exibir erro de download: {e}")
    
    downloader.finished.connect(on_download_finished)
    downloader.error.connect(on_download_error)
    downloader.start()
    
    parent._updater_thread = downloader
    return downloader


def install_update(temp_file, progress_dialog):
    """Instala a atualização baixada"""
    if "--test-update" in sys.argv:
        log("MODO DE TESTE: Simulando instalação...")
        if progress_dialog:
             progress_dialog.status_label.setText("Teste: Atualização simulada!")
             progress_dialog.progress_bar.setValue(100)
             QMessageBox.information(progress_dialog, "Teste", f"Atualização baixada com sucesso em:\n{temp_file}\n\n(Em modo de teste, o arquivo não é substituído)")
        return

    try:
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
        exe_name_no_ext = os.path.splitext(exe_name)[0]
        
        old_exe_backup = os.path.join(exe_dir, f"{exe_name_no_ext}_old.exe")
        
        # Criar script batch
        batch_script = f'''@echo off
setlocal enabledelayedexpansion

timeout /t 3 /nobreak >nul
taskkill /F /IM "{exe_name}" >nul 2>&1

:wait_loop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I /N "{exe_name}">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

timeout /t 2 /nobreak >nul

if exist "{old_exe_backup}" (
    del /F /Q "{old_exe_backup}" >nul 2>&1
)

if exist "{current_exe}" (
    ren "{current_exe}" "{os.path.basename(old_exe_backup)}" >nul 2>&1
)

copy /Y "{temp_file}" "{current_exe}" >nul 2>&1

if exist "{old_exe_backup}" (
    del /F /Q "{old_exe_backup}" >nul 2>&1
)

del /F /Q "{temp_file}" >nul 2>&1
exit
'''
        
        batch_file = os.path.join(tempfile.gettempdir(), "update_gamesstore.bat")
        with open(batch_file, 'w') as f:
            f.write(batch_script)
        
        time.sleep(0.5)
        
        # Mensagem de sucesso
        if progress_dialog:
            progress_dialog.status_label.setText("Atualizado com sucesso!")
            progress_dialog.progress_bar.setValue(100)
            
            QMessageBox.information(
                progress_dialog,
                "Atualização Concluída",
                "O aplicativo foi atualizado com sucesso!\n\nO sistema fechará automaticamente em 5 segundos.\nPor favor, abra o aplicativo novamente para usar a nova versão."
            )
        
        time.sleep(0.5)
        
        log("Executando script de atualizacao...")
        subprocess.Popen(
            batch_file, 
            shell=True, 
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Aguardar 5 segundos antes de fechar
        time.sleep(5.0)
        
        log("Fechando aplicativo para atualizacao...")
        sys.exit(0)
        
    except Exception as e:
        log(f"ERRO ao instalar atualizacao: {e}")
        try:
            QMessageBox.critical(
                progress_dialog.parent() if progress_dialog else None, 
                "Erro na Instalacao", 
                f"Erro ao instalar atualizacao:\n{e}\n\nO arquivo foi baixado em:\n{temp_file}"
            )
        except:
            pass


def check_and_update(parent, show_no_update_message=False, check_beta=False):
    """
    Verifica e aplica atualizações
    
    Args:
        parent: Widget pai
        show_no_update_message: Se True, mostra mensagem quando não há atualizações
        check_beta: Se True, verifica também atualizações beta (para versões -old)
    """
    current_version = get_current_version()
    
    if check_beta or "-old" in current_version.lower():
        log("Versão OLD detectada - verificando atualizações beta...")
        has_update, latest_version, download_url, release_notes = check_for_beta_updates()
        
        if has_update:
            dialog = ModernUpdateDialog(parent, latest_version, release_notes)
            dialog.exec_()
            return perform_update(parent, download_url)
    
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