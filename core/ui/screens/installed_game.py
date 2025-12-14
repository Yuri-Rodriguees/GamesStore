"""
Tela de jogo instalado - InstalledGameScreen
"""
import os
import json
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel, QMessageBox
)

from utils import log_message
from core.workers.image import ImageLoader


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
