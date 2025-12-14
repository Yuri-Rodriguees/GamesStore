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
        
        # Cache de imagens otimizado (limite de 100 imagens)
        self.image_cache = {}
        self.image_cache['__parent_app'] = self
        self._max_cache_size = 100
        
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
        self.tela_manual_install = ManualInstallScreen(self)
        self.tela_download = None
        self.tela_detalhes = None
        self.tela_installed_game = None
        
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
        
        self.list_widget = QListWidget()
        self.list_widget.setVisible(False)
        
        if not hasattr(self, 'search_input'):
            self.search_input = QLineEdit()
        
        header = self.create_modern_header()
        layout.addWidget(header)
        
        self.hero_banner = self.create_hero_banner()
        layout.addWidget(self.hero_banner)
        
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
        self.all_games_section = self.create_game_section("🎮 Todos os Jogos", self.all_games_container)
        
        games_layout.addWidget(self.all_games_section)
        games_layout.addStretch()
        
        self.games_scroll_area.setWidget(games_container)
        layout.addWidget(self.games_scroll_area)
        
        self.tela_home.setLayout(layout)
        QTimer.singleShot(100, self.load_games_from_api)

    def create_modern_header(self):
        """Header com busca em tempo real"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(26, 26, 26, 255), stop:1 rgba(26, 26, 26, 0));
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
            QLineEdit:focus { background-color: rgba(255, 255, 255, 0.15); border-color: #47D64E; }
            QLineEdit::placeholder { color: rgba(255, 255, 255, 0.5); }
        """)
        
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        clear_btn = QPushButton("✕", self.search_input)
        clear_btn.setFixedSize(30, 30)
        clear_btn.move(410, 7)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(255, 255, 255, 0.5); border: none; border-radius: 15px; font-size: 16px; }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); color: white; }
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1a1a, stop:1 #2a2a2a);
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #47D64E, stop:1 #5ce36c);
                color: #1F1F1F; border: none; border-radius: 25px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5ce36c, stop:1 #47D64E);
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
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: white; padding-left: 5px;")
        layout.addWidget(title_label)
        
        scroll = QScrollArea()
        scroll.setFixedHeight(280)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { background: #1a1a1a; height: 8px; border-radius: 4px; }
            QScrollBar::handle:horizontal { background: #47D64E; border-radius: 4px; min-width: 30px; }
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
        """Cria card de jogo para a home"""
        card = QFrame()
        card.setFixedSize(180, 275)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame { background: #232323; border-radius: 12px; border: 2px solid transparent; }
            QFrame:hover { background: #2a2a2a; }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        image = QLabel()
        image.setFixedSize(164, 200)
        image.setAlignment(Qt.AlignCenter)
        image.setStyleSheet("QLabel { background: #181d14; border-radius: 8px; }")
        self.load_game_poster(image, game_id)

        font = QFont("Arial", 10, QFont.Bold)
        name = QLabel()
        name.setFont(font)
        
        if len(game_name) > 20:
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            name.setMinimumHeight(38)
            name.setMaximumHeight(55)
        else:
            metrics = QFontMetrics(font)
            elided = metrics.elidedText(game_name, Qt.ElideRight, 164)
            name.setText(elided)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(38)
        
        name.setStyleSheet("QLabel { color: white; padding: 8px 4px 4px 4px; background: transparent; }")

        layout.addWidget(image)
        layout.addSpacing(3)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.on_game_card_clicked(game_id, game_name)
        return card

    def load_game_poster(self, label, app_id):
        """Carrega poster do jogo com cache"""
        label.setText("🎮")
        label.setStyleSheet(label.styleSheet() + " font-size: 48px; color: #47D64E;")
        
        cache_key = f"game_poster_{app_id}"
        urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
        ]
        
        def on_success(pixmap):
            try:
                if label and not label.isHidden() and not pixmap.isNull():
                    scaled = pixmap.scaled(164, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    label.setPixmap(scaled)
            except:
                pass
        
        loader = ImageLoader(urls, cache_key=cache_key, max_size=(200, 250), parent_cache=self.image_cache)
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
        """Dialog de loading"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setFixedSize(400, 200)
        dialog.setStyleSheet("QDialog { background: #1a1a1a; border-radius: 12px; }")
        
        layout = QVBoxLayout(dialog)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel(f"Carregando {game_name}...")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        
        spinner = QLabel("⏳")
        spinner.setFont(QFont("Arial", 48))
        spinner.setAlignment(Qt.AlignCenter)
        spinner.setStyleSheet("color: #47D64E;")
        
        timer = QTimer(dialog)
        timer.timeout.connect(lambda: spinner.setText("⌛" if spinner.text() == "⏳" else "⏳"))
        timer.start(500)
        
        layout.addWidget(spinner)
        layout.addWidget(title)
        
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
        self.hero_banner.setVisible(True)
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
        header.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(26, 26, 26, 255), stop:1 rgba(26, 26, 26, 0)); }
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 20, 30, 20)
        
        title = QLabel("🎮 Meus Jogos Instalados")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        self.installed_count_label = QLabel("0 jogos instalados")
        self.installed_count_label.setFont(QFont("Arial", 12))
        self.installed_count_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        
        btn_manual = QPushButton("📥 Instalar Manualmente")
        btn_manual.setFixedSize(200, 45)
        btn_manual.setCursor(Qt.PointingHandCursor)
        btn_manual.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #47D64E, stop:1 #5ce36c);
                color: #1F1F1F; border: none; border-radius: 22px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5ce36c, stop:1 #6ff57d); }
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
            QScrollBar:vertical { width: 8px; background: #1a1a1a; }
            QScrollBar::handle:vertical { background: #47D64E; border-radius: 4px; }
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

    def load_games_from_api(self):
        """Carrega jogos da API"""
        try:
            response = requests.get(f"{self.api_url_site}/jogos-publicos", timeout=10)
            data = response.json()
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                if jogos:
                    random.shuffle(jogos)
                    self.populate_game_section(self.all_games_container, jogos)
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
        card = QFrame()
        card.setFixedSize(200, 270)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame { background: #232323; border-radius: 14px; border: 2px solid transparent; }
            QFrame:hover { background: #2a2a2a; }
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
        
        badge = QLabel("✔ Instalado", poster)
        badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        badge.setStyleSheet("""
            QLabel { background-color: rgba(46, 204, 113, 0.95); color: #0f2414;
                border-radius: 8px; padding: 4px 10px; }
        """)
        badge.move(8, 8)
        
        font = QFont("Arial", 11, QFont.Bold)
        name = QLabel()
        name.setFont(font)
        
        if len(game_name) > 25:
            name.setText(game_name)
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            name.setMinimumHeight(40)
            name.setMaximumHeight(60)
        else:
            metrics = QFontMetrics(font)
            elided = metrics.elidedText(game_name, Qt.ElideRight, 180)
            name.setText(elided)
            name.setAlignment(Qt.AlignCenter)
            name.setFixedHeight(40)
        
        name.setStyleSheet("QLabel { color: white; padding: 8px 6px 4px 6px; background: transparent; }")
        
        layout.addWidget(poster)
        layout.addSpacing(7)
        layout.addWidget(name)

        card.mousePressEvent = lambda event: self.open_installed_game_modal(game_name, game_info)
        return card

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
