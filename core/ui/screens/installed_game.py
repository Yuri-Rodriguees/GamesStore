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
        """Configura o conteúdo da tela com design moderno"""
        # Header com imagem de fundo e overlay
        header = QFrame()
        header.setFixedHeight(320)
        header.setStyleSheet("background: #121212;")
        
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Container da imagem
        image_container = QWidget()
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # Imagem do header
        header_image = QLabel()
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        header_image.setScaledContents(True)
        
        # Overlay gradiente para texto legível
        overlay = QLabel(header_image)
        overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(18, 18, 18, 0.3),
                stop:0.5 transparent,
                stop:1 #121212
            );
        """)
        
        # Carregar imagem com cache
        if self.game_id:
            cache_key = f"header_{self.game_id}"
            url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.game_id}/header.jpg"
            
            loader = ImageLoader(
                url,
                cache_key=cache_key,
                max_size=(1200, 350),
                parent_cache=self.parent_app.image_cache
            )
            
            def on_header_loaded(pixmap):
                try:
                    if header_image and not pixmap.isNull():
                        header_image.setPixmap(pixmap)
                        overlay.resize(header_image.size())
                except:
                    pass
            
            loader.signals.finished.connect(on_header_loaded)
            loader.signals.error.connect(lambda: None)
            self.parent_app.thread_pool.start(loader)
        
        image_layout.addWidget(header_image)
        header_layout.addWidget(image_container)
        
        # Botão voltar flutuante
        back_btn = QPushButton("← Voltar", header)
        back_btn.setFixedSize(100, 36)
        back_btn.move(20, 20)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.6);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(71, 214, 78, 0.9);
                border-color: #47D64E;
                color: #121212;
            }
        """)
        
        def go_back():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
                    if hasattr(self.parent_app, 'load_installed_games'):
                        self.parent_app.load_installed_games()
            except Exception as e:
                log_message(f"Erro ao voltar: {e}")
        
        back_btn.clicked.connect(go_back)
        
        container_layout.addWidget(header)
        
        # Conteúdo Principal
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 0, 40, 40)
        content_layout.setSpacing(25)
        
        # Título e Status
        top_info = QHBoxLayout()
        
        title = QLabel(self.game_name)
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        status_badge = QLabel(" INSTALADO ")
        status_badge.setFixedHeight(24)
        status_badge.setStyleSheet("""
            background: rgba(71, 214, 78, 0.15);
            color: #47D64E;
            border: 1px solid rgba(71, 214, 78, 0.3);
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            padding: 0 8px;
        """)
        
        top_info.addWidget(title)
        top_info.addSpacing(15)
        top_info.addWidget(status_badge)
        top_info.addStretch()
        
        content_layout.addLayout(top_info)
        
        # Grid de Informações
        info_grid = QHBoxLayout()
        info_grid.setSpacing(40)
        
        def create_info_item(label, value, icon=""):
            item = QWidget()
            l = QVBoxLayout(item)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(4)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #666666; font-size: 12px; font-weight: 600;")
            
            val = QLabel(f"{icon} {value}" if icon else value)
            val.setStyleSheet("color: #E0E0E0; font-size: 14px;")
            
            l.addWidget(lbl)
            l.addWidget(val)
            return item
            
        install_date = self.game_info.get('install_date', 'N/A')
        manifests_count = len(self.game_info.get('paths', {}).get('manifests', []))
        
        info_grid.addWidget(create_info_item("DATA DE INSTALAÇÃO", install_date, "📅"))
        info_grid.addWidget(create_info_item("STEAM APP ID", self.game_id, "🆔"))
        info_grid.addWidget(create_info_item("ARQUIVOS", f"{manifests_count} manifestos", "📦"))
        info_grid.addStretch()
        
        content_layout.addLayout(info_grid)
        content_layout.addSpacing(20)
        
        # Ações
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        play_btn = QPushButton("JOGAR AGORA")
        play_btn.setFixedSize(200, 50)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setStyleSheet("""
            QPushButton {
                background: #47D64E;
                color: #121212;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: #5ce36c;
            }
            QPushButton:pressed {
                background: #3eb845;
            }
        """)
        play_btn.clicked.connect(self.launch_game)
        
        uninstall_btn = QPushButton("Desinstalar")
        uninstall_btn.setFixedSize(140, 50)
        uninstall_btn.setCursor(Qt.PointingHandCursor)
        uninstall_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #888888;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.1);
                color: #ff4444;
                border-color: rgba(255, 68, 68, 0.3);
            }
        """)
        uninstall_btn.clicked.connect(self.uninstall_game)
        
        actions_layout.addWidget(play_btn)
        actions_layout.addWidget(uninstall_btn)
        actions_layout.addStretch()
        
        content_layout.addLayout(actions_layout)
        content_layout.addStretch()
        
        container_layout.addWidget(content)
    
    def launch_game(self, checked=False):
        """Lança o jogo via Steam"""
        try:
            steam_url = f"steam://rungameid/{self.game_id}"
            QDesktopServices.openUrl(QUrl(steam_url))
        except Exception as e:
            log_message(f"[LAUNCH] Erro ao abrir jogo {self.game_id}: {e}", is_error=True)
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
                                    log_message(f"[UNINSTALL] Nao foi possivel remover {file_path}: {remove_err}", is_error=True)
                    
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
                log_message(f"[UNINSTALL] Erro ao desinstalar {self.game_name}: {e}", is_error=True)
                QMessageBox.critical(self.parent_app, "Erro", f"Erro ao desinstalar:\n{e}")
