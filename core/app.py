"""
GameApp - Aplicação principal do Games Store Launcher
Refatorado do xcore.py
"""
import os
import re
import sys
import json
import random
from pathlib import Path

import psutil
import requests

from PyQt5.QtCore import Qt, QTimer, QThreadPool
from PyQt5.QtGui import QFont, QFontMetrics, QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel,
    QLineEdit, QScrollArea, QStackedWidget, QListWidget, QMessageBox,
    QDialog, QGridLayout
)

from version import __version__
from utils import (
    log_message, get_steam_directory, 
    SECRET_KEY, API_URL, API_URL_SITE, AUTH_CODE
)
from ui_components import TitleBar, CircularProgressBar

# Workers
from core.workers.download import DownloadWorker, DownloadWorkerSignals
from core.workers.search import SearchWorker
from core.workers.details import DetailsWorker
from core.workers.image import ImageLoader

# UI
from core.ui.overlays import DownloadProgressOverlay, ManualInstallProgressOverlay
from core.ui.screens.details import GameDetailsScreen
from core.ui.screens.manual_install import ManualInstallScreen
from core.ui.screens.installed_game import InstalledGameScreen


class GameApp(QWidget):
    """Aplicação principal do Games Store Launcher"""
    
    def __init__(self):
        super().__init__()
        
        self.secret_key = SECRET_KEY
        self.api_url = API_URL
        self.api_url_site = API_URL_SITE
        self.auth_code = AUTH_CODE
        
        self.image_cache = {}
        self.image_cache['__parent_app'] = self
        self._max_cache_size = 200
        
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(12)
        
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(200, 200, 1200, 800)
        self.setFixedSize(1200, 800)
        self.setStyleSheet("background: #121212; color: white;")
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        self.setWindowTitle(f"Games Store v{__version__}")
        
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
        
        self.init_ui()
        
        QTimer.singleShot(0, self.get_steam_directory)
        
        # Verificar atualizações
        from updater import check_and_update
        QTimer.singleShot(2000, lambda: check_and_update(self))
    
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
        self.tela_configuracoes = QWidget()
        self.tela_manual_install = ManualInstallScreen(self)
        self.tela_download = None
        self.tela_detalhes = None
        self.tela_installed_game = None
        
        self.pages.addWidget(self.tela_home)
        self.pages.addWidget(self.tela_jogos)
        self.pages.addWidget(self.tela_dlcs)
        self.pages.addWidget(self.tela_configuracoes)
        self.manual_install_index = self.pages.addWidget(self.tela_manual_install)
        
        content.addWidget(self.pages, 4)
        main_layout.addLayout(content)
        
        # Setup das páginas
        self.setup_home()
        self.setup_jogos()
        self.setup_dlcs()
        self.setup_configuracoes()
    
    def create_sidebar(self):
        """Cria menu lateral moderno e minimalista"""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame {
                background: #121212;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 24, 0, 24)
        layout.setSpacing(4)
        
        # Botões de navegação
        self.sidebar_buttons = []
        
        self.btn_home = self.create_menu_button("🏠", "Home", 0)
        self.btn_games = self.create_menu_button("🎮", "Meus Jogos", 1)
        self.btn_dlcs = self.create_menu_button("📦", "DLCs", 2)
        self.btn_config = self.create_menu_button("⚙", "Configuracões", 3)
        
        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_games)
        layout.addWidget(self.btn_dlcs)
        layout.addStretch()
        layout.addWidget(self.btn_config)
        
        # Ativar primeiro botão por padrão
        self.btn_home.setProperty("active", True)
        self._update_sidebar_style(self.btn_home)
        
        return sidebar
    
    def create_menu_button(self, icon, text, page_index):
        """Cria botão estilizado do menu com indicador ativo"""
        btn = QPushButton(f"  {icon}   {text}")
        btn.setFixedHeight(48)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont("Arial", 11))
        btn.setProperty("active", False)
        btn.setProperty("page_index", page_index)
        
        self._update_sidebar_style(btn)
        
        btn.clicked.connect(lambda: self._on_sidebar_click(btn, page_index))
        self.sidebar_buttons.append(btn) if hasattr(self, 'sidebar_buttons') else None
        
        return btn
    
    def _on_sidebar_click(self, clicked_btn, page_index):
        """Handler de clique na sidebar"""
        self.pages.setCurrentIndex(page_index)
        
        # Atualizar estado ativo
        for btn in [self.btn_home, self.btn_games, self.btn_dlcs, self.btn_config]:
            btn.setProperty("active", btn == clicked_btn)
            self._update_sidebar_style(btn)
    
    def _update_sidebar_style(self, btn):
        """Atualiza estilo do botão baseado no estado"""
        is_active = btn.property("active")
        
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(71, 214, 78, 0.15),
                        stop:1 transparent
                    );
                    color: #47D64E;
                    border: none;
                    border-left: 3px solid #47D64E;
                    border-radius: 0px;
                    text-align: left;
                    padding-left: 20px;
                    font-weight: 600;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgba(255, 255, 255, 0.6);
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    text-align: left;
                    padding-left: 20px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.05);
                    color: rgba(255, 255, 255, 0.9);
                }
            """)
    
    # ========================================================================
    # SEÇÃO 2: HOME PAGE
    # ========================================================================
    
    def setup_home(self):
        """Setup com apenas uma seção de jogos"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.list_widget = QListWidget()
        self.list_widget.setVisible(False)
        
        if not hasattr(self, 'search_input'):
            self.search_input = QLineEdit()
        
        header = self.create_modern_header()
        layout.addWidget(header)
        
        self.search_results_main_container = QScrollArea()
        self.search_results_main_container.setWidgetResizable(True)
        self.search_results_main_container.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.search_results_main_container.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: #1a1a1a; }
            QScrollBar::handle:vertical { background: #47D64E; border-radius: 4px; }
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
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1a1a1a; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #47D64E; border-radius: 4px; min-height: 30px; }
        """)
        
        games_container = QWidget()
        games_layout = QVBoxLayout(games_container)
        games_layout.setContentsMargins(20, 20, 20, 20)
        games_layout.setSpacing(30)
        
        self.all_games_container = QWidget()
        self.all_games_section = self.create_game_section("Todos os Jogos", self.all_games_container)
        
        self.popular_games_container = QWidget()
        self.popular_games_section = self.create_game_section("Jogos Populares", self.popular_games_container)
        
        games_layout.addWidget(self.all_games_section)
        games_layout.addWidget(self.popular_games_section)
        games_layout.addStretch()
        
        self.games_scroll_area.setWidget(games_container)
        layout.addWidget(self.games_scroll_area)
        
        self.tela_home.setLayout(layout)
        QTimer.singleShot(100, self.load_games_from_api)

    def create_modern_header(self):
        """Header minimalista com busca em tempo real"""
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 16, 24, 16)
        
        # Campo de busca moderno
        self.search_input.setPlaceholderText("Buscar jogos...")
        self.search_input.setFixedHeight(42)
        self.search_input.setFixedWidth(400)
        self.search_input.setFont(QFont("Arial", 11))
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: none;
                border-radius: 12px;
                padding: 10px 40px 10px 18px;
                color: white;
            }
            QLineEdit:focus {
                background: rgba(255, 255, 255, 0.1);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.4);
            }
        """)
        
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        clear_btn = QPushButton("✕", self.search_input)
        clear_btn.setFixedSize(28, 28)
        clear_btn.move(365, 7)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.4);
                border: none;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        clear_btn.clicked.connect(self.clear_search)
        clear_btn.hide()
        self.clear_search_btn = clear_btn
        
        layout.addWidget(self.search_input)
        layout.addStretch()
        
        return header
    
    def create_game_section(self, title, container):
        """Seção de jogos com scroll horizontal"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("", 16))
        title_label.setStyleSheet("color: white; padding-left: 5px;")
        layout.addWidget(title_label)
        
        scroll = QScrollArea()
        scroll.setFixedHeight(300)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { 
                height: 6px; 
                background: transparent;
                margin: 0;
            }
            QScrollBar::handle:horizontal { 
                background: rgba(255, 255, 255, 0.15); 
                border-radius: 3px;
                min-width: 40px;
            }
            QScrollBar::handle:horizontal:hover { 
                background: rgba(255, 255, 255, 0.25); 
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
        """)
        
        cards_layout = QHBoxLayout(container)
        cards_layout.setContentsMargins(5, 5, 5, 5)
        cards_layout.setSpacing(15)
        cards_layout.setAlignment(Qt.AlignLeft)
        cards_layout.addStretch()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return section

    def create_game_card(self, game_name, game_id):
        """Cria card de jogo moderno e minimalista"""
        card = QFrame()
        card.setFixedSize(185, 280)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame {
                background: #1E1E1E;
                border-radius: 16px;
            }
            QFrame:hover {
                background: #252525;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(0)

        # Container da imagem
        image_container = QFrame()
        image_container.setFixedSize(165, 205)
        image_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a2518,
                    stop:1 #0f1a0d
                );
                border-radius: 12px;
            }
        """)
        
        image = QLabel(image_container)
        image.setFixedSize(165, 205)
        image.setAlignment(Qt.AlignCenter)
        image.setStyleSheet("QLabel { background: transparent; border-radius: 12px; }")
        self.load_game_poster(image, game_id)

        font = QFont("Segoe UI", 10, QFont.DemiBold)
        name = QLabel()
        name.setFont(font)
        
        if len(game_name) > 22:
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            name.setMinimumHeight(40)
            name.setMaximumHeight(52)
        else:
            metrics = QFontMetrics(font)
            elided = metrics.elidedText(game_name, Qt.ElideRight, 155)
            name.setText(elided)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(40)
        
        name.setStyleSheet("QLabel { color: white; padding: 10px 4px 0px 4px; background: transparent; }")

        layout.addWidget(image_container)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.on_game_card_clicked(game_id, game_name)
        return card

    def load_game_poster(self, label, app_id):
        """Carrega poster do jogo com cache - otimizado"""
        # Placeholder minimalista
        label.setStyleSheet("QLabel { background: #1a2518; border-radius: 12px; }")
        
        cache_key = f"poster_{app_id}"
        
        # URLs em ordem de preferencia (header eh menor e mais rapido)
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
        ]
        
        def on_success(pixmap):
            try:
                if label and not pixmap.isNull():
                    scaled = pixmap.scaled(164, 200, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)
                    label.setPixmap(scaled)
                    label.setStyleSheet("QLabel { background: transparent; border-radius: 12px; }")
            except:
                pass
        
        loader = ImageLoader(urls, cache_key=cache_key, max_size=(180, 220), parent_cache=self.image_cache)
        loader.signals.finished.connect(on_success)
        loader.signals.error.connect(lambda: None)
        self.thread_pool.start(loader)

    def on_game_card_clicked(self, game_id, game_name):
        """Abre tela de detalhes"""
        loading_dialog = self.create_loading_dialog(game_name)
        loading_dialog.show()
        
        worker = DetailsWorker(game_id, self.api_url_site)
        
        def on_success(details):
            loading_dialog.close()
            if hasattr(self, 'tela_detalhes') and self.tela_detalhes:
                try:
                    self.pages.removeWidget(self.tela_detalhes)
                    self.tela_detalhes.deleteLater()
                except:
                    pass
            
            self.tela_detalhes = GameDetailsScreen(self, game_id, details)
            details_index = self.pages.addWidget(self.tela_detalhes)
            self.pages.setCurrentIndex(details_index)
        
        def on_error(error_msg):
            loading_dialog.close()
            QMessageBox.warning(self, "Erro", f"Não foi possível carregar detalhes:\n{error_msg}")
        
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        self.thread_pool.start(worker)

    def create_loading_dialog(self, game_name):
        """Dialog de loading moderno e minimalista"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setFixedSize(320, 140)
        dialog.setStyleSheet("QDialog { background: #121212; border-radius: 12px; }")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignCenter)
        
        # Indicador de loading (pontos animados)
        self._loading_dots = 0
        indicator = QLabel()
        indicator.setFixedHeight(8)
        indicator.setStyleSheet("background: transparent;")
        indicator.setAlignment(Qt.AlignCenter)
        
        # Container para os 3 pontos
        dots_container = QWidget()
        dots_layout = QHBoxLayout(dots_container)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(8)
        dots_layout.setAlignment(Qt.AlignCenter)
        
        self._dot_labels = []
        for i in range(3):
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet("background: #333333; border-radius: 4px;")
            dots_layout.addWidget(dot)
            self._dot_labels.append(dot)
        
        # Titulo
        title = QLabel("Carregando...")
        title.setFont(QFont("", 12))
        title.setStyleSheet("color: #888888;")
        title.setAlignment(Qt.AlignCenter)
        
        # Subtitulo com nome do jogo
        if len(game_name) > 35:
            game_name = game_name[:32] + "..."
        subtitle = QLabel(game_name)
        subtitle.setFont(QFont("", 10))
        subtitle.setStyleSheet("color: #555555;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(dots_container)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        
        # Animacao dos pontos
        def animate_dots():
            self._loading_dots = (self._loading_dots + 1) % 3
            for i, dot in enumerate(self._dot_labels):
                if i == self._loading_dots:
                    dot.setStyleSheet("background: #47D64E; border-radius: 4px;")
                else:
                    dot.setStyleSheet("background: #333333; border-radius: 4px;")
        
        timer = QTimer(dialog)
        timer.timeout.connect(animate_dots)
        timer.start(300)
        
        return dialog

    # ========================================================================
    # SEÇÃO 3: BUSCA
    # ========================================================================

    def on_search_text_changed(self, text):
        """Callback quando texto muda"""
        if hasattr(self, 'clear_search_btn'):
            self.clear_search_btn.setVisible(len(text) > 0)
        
        if len(text) >= 3:
            self.search_timer.start()
            self.games_scroll_area.setVisible(False)
            self.search_results_main_container.setVisible(True)
        else:
            self.search_timer.stop()
            self.games_scroll_area.setVisible(True)
            self.search_results_main_container.setVisible(False)

    def perform_search(self):
        """Executa busca na API"""
        query = self.search_input.text().strip()
        if len(query) < 3:
            return
        
        self.show_search_loading()
        url = f"{self.api_url_site}/buscar-jogos-loja?q={query}"
        
        worker = SearchWorker(url)
        worker.signals.finished.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        self.thread_pool.start(worker)

    def show_search_loading(self):
        """Loading de busca"""
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

    def on_search_complete(self, results):
        """Processa resultados"""
        while self.search_cards_layout.count():
            item = self.search_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not results:
            self.search_results_title.setText("Nenhum resultado encontrado")
            return
        
        query = self.search_input.text().strip()
        self.search_results_title.setText(f'🔍 Resultados para "{query}" ({len(results)} encontrados)')
        
        for i, game in enumerate(results[:18]):
            row = i // 4
            col = i % 4
            card = self.create_game_card(game['nome'], str(game['appid']))
            self.search_cards_layout.addWidget(card, row, col)

    def on_search_error(self, error_msg):
        """Trata erros de busca"""
        while self.search_cards_layout.count():
            item = self.search_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        error_label = QLabel(f"⚠️ Erro: {error_msg}")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: #ff4444; padding: 20px;")
        self.search_cards_layout.addWidget(error_label, 0, 0, 1, 6)

    def clear_search(self):
        """Limpa busca"""
        self.search_input.clear()
        self.games_scroll_area.setVisible(True)
        self.search_results_main_container.setVisible(False)

    # ========================================================================
    # SEÇÃO 4: DOWNLOADS
    # ========================================================================

    def start_download_from_api(self, game_id, game_name):
        """Inicia download"""
        steam_path = self.get_steam_directory()
        if not steam_path:
            QMessageBox.critical(self, "Erro", "Steam não encontrada!")
            return

        download_url = f"https://generator.ryuu.lol/secure_download?appid={game_id}&auth_code=RYUUMANIFESTtsl1c9"

        try:
            progress_dialog = DownloadProgressOverlay(self, game_name)
            worker = DownloadWorker(game_id, download_url, game_name, steam_path)
            progress_dialog.worker = worker
            
            worker.signals.progress.connect(progress_dialog.progress_bar.set_value)
            worker.signals.status.connect(progress_dialog.status_label.setText)
            worker.signals.speed.connect(progress_dialog.progress_bar.set_speed)
            worker.signals.downloaded.connect(progress_dialog.progress_bar.set_downloaded)
            worker.signals.success.connect(progress_dialog.on_download_success)
            worker.signals.error.connect(progress_dialog.on_download_error)
            
            self.thread_pool.start(worker)
            result = progress_dialog.exec_()
            
            if result == QDialog.Accepted:
                QTimer.singleShot(500, self.ask_restart_steam)
                QTimer.singleShot(1000, lambda: self.pages.setCurrentIndex(1))
                QTimer.singleShot(1200, self.load_installed_games)
        except Exception as e:
            log_message(f"[START_DOWNLOAD] ERRO: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar download:\n{str(e)}")

    # ========================================================================
    # SEÇÃO 5: SETUP JOGOS E DLCS
    # ========================================================================

    def setup_jogos(self):
        """Tela de jogos instalados"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("QFrame { background: transparent; }")
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 20, 30, 20)
        
        title = QLabel("Meus Jogos Instalados")
        title.setFont(QFont("", 20))
        title.setStyleSheet("color: white;")
        
        self.installed_count_label = QLabel("0 jogos instalados")
        self.installed_count_label.setFont(QFont("", 11))
        self.installed_count_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        
        btn_manual = QPushButton("Instalar Manualmente")
        btn_manual.setFixedSize(180, 42)
        btn_manual.setCursor(Qt.PointingHandCursor)
        btn_manual.setFont(QFont("", 11))
        btn_manual.setStyleSheet("""
            QPushButton { 
                background: #47D64E;
                color: #0D0D0D; 
                border: none; 
                border-radius: 8px;
            }
            QPushButton:hover { background: #5CE36C; }
        """)
        btn_manual.clicked.connect(self.open_manual_install_dialog)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.installed_count_label)
        header_layout.addSpacing(15)
        header_layout.addWidget(btn_manual)
        
        layout.addWidget(header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { 
                width: 6px; 
                background: transparent;
                margin: 0;
            }
            QScrollBar::handle:vertical { 
                background: rgba(255, 255, 255, 0.15); 
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { 
                background: rgba(255, 255, 255, 0.25); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
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

    def setup_dlcs(self):
        """Setup da página de DLCs"""
        layout = QVBoxLayout()
        label = QLabel("DLCs em breve!")
        label.setFont(QFont("Arial", 16, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.tela_dlcs.setLayout(layout)
    
    def setup_configuracoes(self):
        """Setup da página de Configurações"""
        layout = QVBoxLayout(self.tela_configuracoes)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)
        
        # Header
        title = QLabel("Configuracões")
        title.setFont(QFont("", 22))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        layout.addSpacing(8)
        
        subtitle = QLabel("Gerencie as configuracões do aplicativo")
        subtitle.setFont(QFont("", 11))
        subtitle.setStyleSheet("color: #666666;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(40)
        
        # Secao DF-Tools
        section_title = QLabel("DF-Tools")
        section_title.setFont(QFont("", 13))
        section_title.setStyleSheet("color: #47D64E;")
        layout.addWidget(section_title)
        
        layout.addSpacing(12)
        
        desc = QLabel("Arquivos necessarios para o funcionamento dos jogos")
        desc.setFont(QFont("", 10))
        desc.setStyleSheet("color: #555555;")
        layout.addWidget(desc)
        
        layout.addSpacing(24)
        
        # Status items
        self.status_hid = self.create_status_row("Driver de Controle")
        layout.addWidget(self.status_hid)
        
        layout.addSpacing(12)
        
        self.status_cef = self.create_status_row("Configuração de Componentes")
        layout.addWidget(self.status_cef)
        
        layout.addSpacing(32)
        
        # Botoes
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(16)
        
        self.btn_verificar = QPushButton("Verificar")
        self.btn_verificar.setFixedHeight(42)
        self.btn_verificar.setMinimumWidth(130)
        self.btn_verificar.setCursor(Qt.PointingHandCursor)
        self.btn_verificar.setFont(QFont("", 11))
        self.btn_verificar.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover { 
                border-color: #555555;
                color: white;
            }
        """)
        self.btn_verificar.clicked.connect(self.verificar_dftools)
        
        self.btn_instalar_dftools = QPushButton("Instalar Arquivos")
        self.btn_instalar_dftools.setFixedHeight(42)
        self.btn_instalar_dftools.setMinimumWidth(150)
        self.btn_instalar_dftools.setCursor(Qt.PointingHandCursor)
        self.btn_instalar_dftools.setFont(QFont("", 11))
        self.btn_instalar_dftools.setStyleSheet("""
            QPushButton {
                background: #47D64E;
                color: #0D0D0D;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover { background: #5CE36C; }
        """)
        self.btn_instalar_dftools.clicked.connect(self.instalar_dftools)
        
        btn_layout.addWidget(self.btn_verificar)
        btn_layout.addWidget(self.btn_instalar_dftools)
        btn_layout.addStretch()
        
        layout.addWidget(btn_container)
        layout.addStretch()
        
        # Verificar status inicial
        QTimer.singleShot(500, self.verificar_dftools)
    
    def create_status_row(self, filename):
        """Cria linha de status para arquivo"""
        container = QWidget()
        container.setFixedHeight(36)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Indicador
        indicator = QLabel()
        indicator.setFixedSize(8, 8)
        indicator.setStyleSheet("background: #333333; border-radius: 4px;")
        indicator.setObjectName("indicator")
        
        # Nome do arquivo
        name = QLabel(filename)
        name.setFont(QFont("", 10))
        name.setStyleSheet("color: #888888;")
        name.setObjectName("name")
        
        # Status
        status = QLabel("Verificando...")
        status.setFont(QFont("", 10))
        status.setStyleSheet("color: #555555;")
        status.setAlignment(Qt.AlignRight)
        status.setObjectName("status")
        
        layout.addWidget(indicator)
        layout.addWidget(name)
        layout.addStretch()
        layout.addWidget(status)
        
        return container
    
    def create_status_item(self, name, installed):
        """Cria item de status para verificacao"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Icone de status
        icon = QLabel()
        icon.setFixedSize(20, 20)
        icon.setAlignment(Qt.AlignCenter)
        icon.setObjectName(f"icon_{name.replace('.', '_')}")
        
        # Nome do arquivo
        label = QLabel(name)
        label.setFont(QFont("", 10))
        label.setStyleSheet("color: #AAAAAA;")
        label.setObjectName(f"label_{name.replace('.', '_')}")
        
        # Status text
        status = QLabel("Verificando...")
        status.setFont(QFont("", 10))
        status.setStyleSheet("color: #888888;")
        status.setObjectName(f"status_{name.replace('.', '_')}")
        
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(status)
        
        return container
    
    def update_status_item(self, container, installed):
        """Atualiza visual do item de status"""
        indicator = container.findChild(QLabel, "indicator")
        status = container.findChild(QLabel, "status")
        name_label = container.findChild(QLabel, "name")
        
        if installed:
            indicator.setStyleSheet("background: #47D64E; border-radius: 4px;")
            status.setText("Instalado")
            status.setStyleSheet("color: #47D64E;")
            name_label.setStyleSheet("color: white;")
        else:
            indicator.setStyleSheet("background: #FF4444; border-radius: 4px;")
            status.setText("Nao encontrado")
            status.setStyleSheet("color: #FF4444;")
            name_label.setStyleSheet("color: #888888;")
    
    def verificar_dftools(self, checked=False):
        """Verifica se os arquivos DF-Tools estao instalados"""
        # Mostrar loading
        self.set_status_loading(self.status_hid)
        self.set_status_loading(self.status_cef)
        
        # Delay para simular loading e permitir UI atualizar
        QTimer.singleShot(500, self._verificar_dftools_real)
    
    def _verificar_dftools_real(self):
        """Executa a verificacao real"""
        if not self.steam_path:
            log_message("[DFTOOLS] Steam path nao encontrado")
            self.update_status_item(self.status_hid, False)
            self.update_status_item(self.status_cef, False)
            return
        
        steam_dir = Path(self.steam_path)
        
        # Verificar xinput1_4.dll
        hid_path = steam_dir / "xinput1_4.dll"
        hid_installed = hid_path.exists()
        self.update_status_item(self.status_hid, hid_installed)
        
        # Verificar .cef-dev-tools-size.vdf
        cef_path = steam_dir / ".cef-dev-tools-size.vdf"
        cef_installed = cef_path.exists()
        self.update_status_item(self.status_cef, cef_installed)
        
        log_message(f"[DFTOOLS] Verificacao: xinput1_4.dll={hid_installed}, cef={cef_installed}")
    
    def set_status_loading(self, container):
        """Define status como loading"""
        indicator = container.findChild(QLabel, "indicator")
        status = container.findChild(QLabel, "status")
        name_label = container.findChild(QLabel, "name")
        
        indicator.setStyleSheet("background: #555555; border-radius: 4px;")
        status.setText("Verificando...")
        status.setStyleSheet("color: #555555;")
        name_label.setStyleSheet("color: #666666;")
    
    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def instalar_dftools(self, checked=False):
        """Instala os arquivos DF-Tools na pasta da Steam"""
        if not self.steam_path:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erro", "Pasta da Steam nao encontrada!")
            return
        
        steam_dir = Path(self.steam_path)
        
        try:
            import shutil
            
            # Caminhos dos arquivos fonte (dentro do EXE ou pasta local)
            hid_source = Path(self.resource_path("config/xinput1_4.dll"))
            cef_source = Path(self.resource_path("config/.cef-dev-tools-size.vdf"))
            
            # Copiar xinput1_4.dll
            hid_dest = steam_dir / "xinput1_4.dll"
            
            if hid_source.exists():
                shutil.copy2(hid_source, hid_dest)
                log_message(f"[DFTOOLS] xinput1_4.dll copiado para {hid_dest}")
            else:
                log_message(f"[DFTOOLS] ERRO: xinput1_4.dll nao encontrado em {hid_source}")
            
            # Copiar .cef-dev-tools-size.vdf
            cef_dest = steam_dir / ".cef-dev-tools-size.vdf"
            
            if cef_source.exists():
                shutil.copy2(cef_source, cef_dest)
                log_message(f"[DFTOOLS] .cef-dev-tools-size.vdf copiado para {cef_dest}")
            else:
                log_message(f"[DFTOOLS] ERRO: .cef-dev-tools-size.vdf nao encontrado em {cef_source}")
            
            # Verificar novamente
            self.verificar_dftools()
            
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Sucesso", "Arquivos DF-Tools instalados com sucesso!")
            
        except PermissionError as e:
            log_message(f"[DFTOOLS] Erro de permissao: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Steam em uso", 
                "Nao foi possivel instalar os arquivos.\n\n"
                "Feche a Steam completamente e tente novamente.")
                
        except OSError as e:
            if e.winerror == 32:  # Arquivo em uso
                log_message(f"[DFTOOLS] Arquivo em uso: {e}")
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Steam em uso", 
                    "Nao foi possivel instalar os arquivos.\n\n"
                    "Feche a Steam completamente e tente novamente.")
            else:
                log_message(f"[DFTOOLS] Erro OS: {e}")
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Erro", f"Erro ao instalar arquivos:\n{e}")
            
        except Exception as e:
            log_message(f"[DFTOOLS] Erro ao instalar: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erro", f"Erro ao instalar arquivos:\n{e}")

    def load_games_from_api(self):
        """Carrega jogos da API"""
        try:
            response = requests.get(f"{self.api_url_site}/jogos-publicos", timeout=10)
            data = response.json()
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                if jogos:
                    # Todos os jogos - ordem aleatoria
                    jogos_all = jogos.copy()
                    random.shuffle(jogos_all)
                    self.populate_game_section(self.all_games_container, jogos_all)
                    
                    # Jogos populares - outra ordem aleatoria
                    jogos_popular = jogos.copy()
                    random.shuffle(jogos_popular)
                    self.populate_game_section(self.popular_games_container, jogos_popular)
        except Exception as e:
            log_message(f"Erro ao carregar jogos: {e}")

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

    def load_installed_games(self):
        """Carrega jogos instalados"""
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
            log_message(f"Erro ao carregar jogos instalados: {e}")
            self.show_no_games_installed()

    def create_installed_game_card(self, game_name, game_info):
        """Cria card de jogo instalado"""
        # Limpar caracteres especiais do nome
        clean_name = self.clean_game_name(game_name)
        
        card = QFrame()
        card.setFixedSize(200, 270)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame { background: #1E1E1E; border-radius: 14px; }
            QFrame:hover { background: #252525; }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        poster = QLabel()
        poster.setFixedSize(180, 210)
        poster.setAlignment(Qt.AlignCenter)
        poster.setStyleSheet("QLabel { background: #131a12; border-radius: 10px; }")
        game_id = game_info.get('id', '')
        self.load_game_poster(poster, game_id)
        
        badge = QLabel("Instalado", poster)
        badge.setFont(QFont("", 9))
        badge.setStyleSheet("""
            QLabel { 
                background-color: rgba(71, 214, 78, 0.9); 
                color: #0D0D0D;
                border-radius: 6px; 
                padding: 4px 10px;
            }
        """)
        badge.move(8, 8)
        
        name = QLabel()
        name.setFont(QFont("", 10))
        
        if len(clean_name) > 25:
            name.setText(clean_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            name.setMinimumHeight(40)
            name.setMaximumHeight(60)
        else:
            metrics = QFontMetrics(QFont("", 10))
            elided = metrics.elidedText(clean_name, Qt.ElideRight, 180)
            name.setText(elided)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(40)
        
        name.setStyleSheet("QLabel { color: white; padding: 8px 6px 4px 6px; background: transparent; }")
        
        layout.addWidget(poster)
        layout.addSpacing(7)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.open_installed_game_modal(game_name, game_info)
        return card
    
    def clean_game_name(self, name):
        """Limpa caracteres especiais do nome do jogo"""
        # Remover caracteres problemáticos de encoding
        replacements = {
            'â„¢': '',
            'Â®': '',
            'â€™': "'",
            'â€"': '-',
            'â€œ': '"',
            'â€': '"',
            'Ã©': 'e',
            'Ã ': 'a',
            'Ã¡': 'a',
            'Ã£': 'a',
            'Ã§': 'c',
            'Ãº': 'u',
            'Ã³': 'o',
            'Ã­': 'i',
        }
        for old, new in replacements.items():
            name = name.replace(old, new)
        return name.strip()

    def show_no_games_installed(self):
        """Mostra estado vazio"""
        while self.installed_games_layout.count():
            item = self.installed_games_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.installed_count_label.setText("0 jogos instalados")
        
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
        
        empty_layout.addWidget(icon)
        empty_layout.addWidget(text)
        
        self.installed_games_layout.addWidget(empty, 0, 0, 1, 5)

    def open_installed_game_modal(self, game_name, game_info):
        """Abre tela do jogo instalado"""
        try:
            if self.tela_installed_game:
                try:
                    self.pages.removeWidget(self.tela_installed_game)
                    self.tela_installed_game.deleteLater()
                except:
                    pass
            
            self.tela_installed_game = InstalledGameScreen(self, game_name, game_info)
            installed_index = self.pages.addWidget(self.tela_installed_game)
            self.pages.setCurrentIndex(installed_index)
        except Exception as e:
            log_message(f"Erro ao abrir tela: {e}")
            QMessageBox.critical(self, "Erro", f"Erro:\n{str(e)}")

    def open_manual_install_dialog(self, checked=False):
        """Abre tela de instalação manual"""
        try:
            if self.manual_install_index is not None:
                self.pages.setCurrentIndex(self.manual_install_index)
        except Exception as e:
            log_message(f"Erro: {e}")

    def install_manual_game(self, filepath):
        """Instala jogo manualmente"""
        try:
            if not self.steam_path:
                self.steam_path = self.get_steam_directory()
            
            if not self.steam_path:
                QMessageBox.critical(self, "Erro", "Steam não encontrada!")
                return
            
            filename = os.path.basename(filepath)
            match = re.match(r"^(.+?)\s*\((\d+)\)\.(zip|rar)$", filename, re.IGNORECASE)
            
            if not match:
                QMessageBox.critical(self, "Erro de Formato", f"Nome de arquivo inválido!\nEsperado: Nome do Jogo (ID).zip ou .rar")
                return
            
            game_name = match.group(1).strip()
            game_id = match.group(2)
            
            progress_dialog = ManualInstallProgressOverlay(self, game_id, game_name, filepath, self.steam_path)
            progress_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao instalar jogo:\n{str(e)}")

    # ========================================================================
    # SEÇÃO 6: STEAM
    # ========================================================================

    def get_steam_directory(self):
        """Detecta diretório da Steam"""
        steam_path = get_steam_directory()
        if steam_path:
            self.steam_path = steam_path.replace("/", "\\")
        return self.steam_path

    def restart_steam(self):
        """Reinicia a Steam"""
        try:
            current_pid = os.getpid()
            steam_names = ["steam.exe", "steamwebhelper.exe"]
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                    if any(n in proc_name for n in steam_names):
                        proc_obj = psutil.Process(proc.info['pid'])
                        proc_obj.terminate()
                        try:
                            proc_obj.wait(timeout=3)
                        except:
                            proc_obj.kill()
                except:
                    continue
            
            QTimer.singleShot(1800, self.open_steam_url)
        except Exception as e:
            log_message(f"Erro ao reiniciar Steam: {e}")

    def open_steam_url(self):
        """Abre a Steam"""
        try:
            if getattr(sys, 'frozen', False):
                import subprocess
                subprocess.Popen(['cmd', '/c', 'start', '', 'steam://open/main'],
                    creationflags=0x00000008 | 0x00000200,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            else:
                os.startfile("steam://open/main")
        except Exception as e:
            log_message(f"Erro ao abrir Steam: {e}")

    def ask_restart_steam(self):
        """Pergunta se deseja reiniciar Steam"""
        try:
            if not self.isVisible():
                return
            
            reply = QMessageBox.question(self, "Reiniciar Steam",
                "O novo jogo foi instalado!\nDeseja reiniciar a Steam para aparecer na biblioteca?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                QTimer.singleShot(100, self.restart_steam)
        except Exception as e:
            log_message(f"Erro: {e}")

    # ========================================================================
    # SEÇÃO 7: EVENTOS
    # ========================================================================

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.selected_file_path = urls[0].toLocalFile()
    
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
