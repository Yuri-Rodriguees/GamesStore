"""
Tela de detalhes do jogo - GameDetailsScreen
"""
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel, QScrollArea
)

from core.workers.image import ImageLoader


class GameDetailsScreen(QWidget):
    """Tela de detalhes do jogo (convertida de modal para tela real)"""
    
    def __init__(self, parent, game_id, details):
        super().__init__(parent)
        self.game_id = game_id
        self.details = details
        self.parent_app = parent
        
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
        
        # Setup do conteúdo
        self.setup_screen_content(container_layout)
        
        layout.addWidget(self.main_container)
    
    def setup_screen_content(self, layout):
        """Monta o conteúdo da tela"""
        details = self.details
        game_id = self.game_id
        
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
        
        header_image = QLabel()
        header_image.setFixedSize(1200, 300)
        header_image.setAlignment(Qt.AlignCenter)
        header_image.setStyleSheet("background: #1a1a1a;")
        
        if details.get('background') or details.get('header_image'):
            bg_url = details.get('background') or details.get('header_image')
            cache_key = f"game_details_header_{self.game_id}"
            loader = ImageLoader(
                bg_url,
                cache_key=cache_key,
                max_size=(1250, 350),
                parent_cache=self.parent_app.image_cache
            )
            def on_header_loaded(pixmap):
                try:
                    if header_image and not pixmap.isNull():
                        scaled = pixmap.scaled(
                            1200, 300,
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
        
        overlay = QLabel(header)
        overlay.setGeometry(0, 0, 1200, 300)
        overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 transparent,
                stop:1 rgba(26, 26, 26, 0.9)
            );
        """)
        
        # Botão voltar
        back_btn = QPushButton("← Voltar", header)
        back_btn.setFixedSize(100, 40)
        back_btn.move(20, 10)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(71, 214, 78, 0.8);
            }
        """)
        back_btn.clicked.connect(lambda: self.parent_app.pages.setCurrentIndex(1))
        
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
            download_btn.clicked.connect(lambda: self.parent_app.start_download_from_api(game_id, details.get('nome', 'Jogo')))
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
