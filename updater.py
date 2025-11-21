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
        log("⚠️ Modo desenvolvimento - pulando verificação")
        return False, None, None, None
    
    try:
        # Buscar todas as releases (incluindo prereleases)
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
        log(f"Consultando: {api_url}")
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            log(f"ERRO: Status {response.status_code}")
            return False, None, None, None
        
        releases = response.json()
        current_version = get_current_version()
        
        # Procurar por releases beta mais recentes (ignorar -old)
        latest_beta = None
        latest_beta_version = None
        
        for release in releases:
            if not release.get("prerelease", False):
                continue
            
            tag_name = release.get("tag_name", "").replace("v", "")
            
            # Ignorar versões -old (são as versões antigas para teste)
            if "-old" in tag_name.lower():
                continue
            
            # Verificar se tem .exe
            has_exe = False
            download_url = None
            for asset in release.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    has_exe = True
                    download_url = asset.get("browser_download_url")
                    break
            
            if not has_exe:
                continue
            
            # Comparar versões
            try:
                # Limpar versões usando função auxiliar
                current_clean = clean_version(current_version)
                latest_clean = clean_version(tag_name)
                
                current_parts = current_clean.split(".")
                latest_parts = latest_clean.split(".")
                
                # Garantir que ambas têm 3 partes
                while len(current_parts) < 3:
                    current_parts.append("0")
                while len(latest_parts) < 3:
                    latest_parts.append("0")
                
                current_tuple = tuple(map(int, current_parts[:3]))
                latest_tuple = tuple(map(int, latest_parts[:3]))
                
                # Se a versão beta é mais nova que a atual
                if latest_tuple > current_tuple:
                    # Comparar com a versão beta já encontrada (se houver)
                    if latest_beta is None:
                        latest_beta = release
                        latest_beta_version = tag_name
                        log(f"✅ Versão beta encontrada: {tag_name}")
                    else:
                        # Comparar com a versão beta já encontrada
                        existing_clean = clean_version(latest_beta_version)
                        existing_parts = existing_clean.split(".")
                        while len(existing_parts) < 3:
                            existing_parts.append("0")
                        existing_tuple = tuple(map(int, existing_parts[:3]))
                        
                        if latest_tuple > existing_tuple:
                            latest_beta = release
                            latest_beta_version = tag_name
                            log(f"✅ Versão beta mais recente encontrada: {tag_name}")
            except (ValueError, IndexError) as e:
                log(f"⚠️ Erro ao comparar versão {tag_name}: {e}")
                continue
        
        if latest_beta is None:
            log("ℹ️ Nenhuma atualização beta disponível")
            log("=" * 60)
            return False, None, None, None
        
        # Buscar .exe na release beta mais recente
        download_url = None
        for asset in latest_beta.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url")
                log(f"EXE encontrado: {asset.get('name')}")
                break
        
        if not download_url:
            log("ERRO: Nenhum .exe encontrado na release beta")
            return False, None, None, None
        
        log(f"✅ ATUALIZAÇÃO BETA DISPONÍVEL: {current_version} → {latest_beta_version}")
        log("=" * 60)
        
        release_notes = latest_beta.get("body", "Melhorias gerais")
        return True, latest_beta_version, download_url, release_notes
        
def clean_version(version_str):
    """Remove prefixos e sufixos da versão, retornando apenas números"""
    if not version_str:
        return "0.0.0"
    
    try:
        # Encontrar todos os grupos de números na string
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
            # Limpar versões usando função auxiliar
            current_clean = clean_version(current_version)
            latest_clean = clean_version(latest_version)
            
            log(f"Versão atual original: {current_version}")
            log(f"Versão atual limpa: {current_clean}")
            log(f"Versão latest original: {latest_version}")
            log(f"Versão latest limpa: {latest_clean}")
            
            current_parts = current_clean.split(".")
            latest_parts = latest_clean.split(".")
            
            log(f"Partes da versão atual: {current_parts}")
            log(f"Partes da versão latest: {latest_parts}")
            
            # Garantir que ambas têm 3 partes
            while len(current_parts) < 3:
                current_parts.append("0")
            while len(latest_parts) < 3:
                latest_parts.append("0")
            
            log(f"Partes finais da versão atual: {current_parts[:3]}")
            log(f"Partes finais da versão latest: {latest_parts[:3]}")
            
            # Validar que todas as partes são números antes de converter
            for i, part in enumerate(current_parts[:3]):
                if not part.isdigit():
                    log(f"ERRO: Parte {i} da versão atual não é número: '{part}'")
                    raise ValueError(f"Parte da versão não é número: '{part}'")
            
            for i, part in enumerate(latest_parts[:3]):
                if not part.isdigit():
                    log(f"ERRO: Parte {i} da versão latest não é número: '{part}'")
                    raise ValueError(f"Parte da versão não é número: '{part}'")
            
            current = tuple(map(int, current_parts[:3]))
            latest = tuple(map(int, latest_parts[:3]))
            
            has_update = latest > current
            
            if has_update:
                log(f"✅ ATUALIZAÇÃO STABLE DISPONÍVEL: {current_version} → {latest_version}")
            else:
                log(f"ℹ️ JÁ ESTÁ ATUALIZADO")
            
            log("=" * 60)
            return has_update, latest_version, download_url, release_notes
            
        except (ValueError, IndexError) as e:
            log(f"ERRO ao comparar versões: {e}")
            log(f"   Versão atual: {current_version} (limpa: {current_clean})")
            log(f"   Versão latest: {latest_version} (limpa: {latest_clean})")
            return False, None, None, None
        
    except Exception as e:
        log(f"ERRO: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
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
    
    def on_download_finished(temp_file):
        """Callback quando o download termina com sucesso"""
        try:
            # Aguardar um pouco para garantir que o arquivo foi completamente salvo
            QTimer.singleShot(1500, lambda: install_update(temp_file, progress_dialog))
        except Exception as e:
            log(f"ERRO no callback de download: {e}")
            progress_dialog.close()
            QMessageBox.critical(parent, "Erro", f"Erro ao processar download: {e}")
    
    def on_download_error(error_msg):
        """Callback quando ocorre erro no download"""
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
    try:
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
        exe_name_no_ext = os.path.splitext(exe_name)[0]
        
        # Nome do arquivo antigo (backup temporário)
        old_exe_backup = os.path.join(exe_dir, f"{exe_name_no_ext}_old.exe")
        
        # Criar script batch mais robusto que:
        # 1. Aguarda o processo atual terminar completamente
        # 2. Renomeia o executável antigo para backup
        # 3. Move o novo executável para o local correto
        # 4. Remove o backup antigo
        # 5. Inicia o novo executável
        batch_script = f"""@echo off
setlocal enabledelayedexpansion

REM Aguardar um pouco para garantir que o processo atual começou a fechar
timeout /t 3 /nobreak >nul

REM Tentar fechar o processo atual se ainda estiver rodando
taskkill /F /IM "{exe_name}" >nul 2>&1

REM Aguardar o processo terminar completamente
:wait_loop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I /N "{exe_name}">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

REM Aguardar mais um pouco para garantir que todos os arquivos foram liberados
timeout /t 2 /nobreak >nul

REM Se o executável antigo já existe como backup, removê-lo
if exist "{old_exe_backup}" (
    del /F /Q "{old_exe_backup}" >nul 2>&1
)

REM Renomear o executável atual para backup (se existir)
if exist "{current_exe}" (
    ren "{current_exe}" "{os.path.basename(old_exe_backup)}" >nul 2>&1
)

        
        # Aguardar um pouco para garantir que o diálogo fechou
        time.sleep(0.5)
        
        # Fechar todas as janelas antes de sair
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                for widget in app.allWidgets():
                    if widget != progress_dialog:
                        try:
                            widget.close()
                        except:
                            pass
        except:
            pass
        
        # Aguardar um pouco mais para garantir que tudo foi fechado
        time.sleep(0.5)
        
        # Executar o batch
        log("Executando script de atualização...")
        process = subprocess.Popen(
            batch_file, 
            shell=True, 
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Aguardar um pouco para garantir que o processo foi iniciado
        time.sleep(1.0)
        
        # Sair do programa
        log("Fechando aplicativo para atualização...")
        sys.exit(0)
        
    except Exception as e:
        log(f"ERRO ao instalar atualização: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        # Se houver erro, tentar ao menos notificar
        try:
            QMessageBox.critical(
                progress_dialog.parent() if progress_dialog else None, 
                "Erro na Instalação", 
                f"Erro ao instalar atualização:\n{e}\n\nO arquivo foi baixado em:\n{temp_file}\n\nVocê pode fechar este aplicativo e substituir manualmente o executável."
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
    
    # Se a versão atual é -old, verificar atualizações beta primeiro
    if check_beta or "-old" in current_version.lower():
        log("🔍 Versão OLD detectada - verificando atualizações beta...")
        has_update, latest_version, download_url, release_notes = check_for_beta_updates()
        
        if has_update:
            dialog = ModernUpdateDialog(parent, latest_version, release_notes)
            dialog.exec_()
            return perform_update(parent, download_url)
    
    # Verificar atualizações estáveis normais
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