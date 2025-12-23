"""
Tela de detalhes do jogo - GameDetailsScreen
"""
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel, QScrollArea
)

from datax import Styles
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
        """Monta o conteúdo da tela com design moderno"""
        details = self.details
        game_id = self.game_id
        
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
        
        # Overlay gradiente
        overlay = QLabel(header_image)
        overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(18, 18, 18, 0.3),
                stop:0.5 transparent,
                stop:1 #121212
            );
        """)
        
        if details.get('background') or details.get('header_image'):
            bg_url = details.get('background') or details.get('header_image')
            cache_key = f"game_details_header_{self.game_id}"
            loader = ImageLoader(
                bg_url,
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
        back_btn.setStyleSheet(Styles.details_back_btn)
        back_btn.clicked.connect(lambda: self.parent_app.pages.setCurrentIndex(1))
        
        layout.addWidget(header)
        
        # Scroll de conteúdo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: #1a1a1a; }
            QScrollBar::handle:vertical { background: #333; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #47D64E; }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 0, 40, 40)
        content_layout.setSpacing(25)
        
        # Título e Status
        top_info = QHBoxLayout()
        
        title = QLabel(details.get('nome', 'Jogo'))
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)
        
        disponivel = details.get('disponivel_download', False)
        
        status_text = "DISPONÍVEL" if disponivel else "INDISPONÍVEL"
        status_color = "#47D64E" if disponivel else "#ff4444"
        status_bg = "rgba(71, 214, 78, 0.15)" if disponivel else "rgba(255, 68, 68, 0.15)"
        
        status_badge = QLabel(f" {status_text} ")
        status_badge.setFixedHeight(24)
        status_badge.setStyleSheet(f"""
            background: {status_bg};
            color: {status_color};
            border: 1px solid {status_color}40;
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
            val.setWordWrap(True)
            
            l.addWidget(lbl)
            l.addWidget(val)
            return item
        
        # Dados para o grid
        release_date = details.get('data_lancamento', 'N/A')
        devs = ', '.join(details['desenvolvedores']) if isinstance(details.get('desenvolvedores'), list) else details.get('desenvolvedores', 'N/A')
        genres = ', '.join(details['generos']) if isinstance(details.get('generos'), list) else details.get('generos', 'N/A')
        
        # Limitar tamanho dos textos
        if len(devs) > 30: devs = devs[:27] + "..."
        if len(genres) > 30: genres = genres[:27] + "..."
        
        info_grid.addWidget(create_info_item("LANÇAMENTO", release_date, "📅"))
        info_grid.addWidget(create_info_item("DESENVOLVEDOR", devs, "👨‍💻"))
        info_grid.addWidget(create_info_item("GÊNEROS", genres, "📂"))
        info_grid.addStretch()
        
        content_layout.addLayout(info_grid)
        content_layout.addSpacing(10)
        
        # Descrição
        desc_label = QLabel("SOBRE O JOGO")
        desc_label.setStyleSheet("color: #666666; font-size: 12px; font-weight: 600; margin-bottom: 5px;")
        content_layout.addWidget(desc_label)
        
        desc = QLabel(details.get('descricao', 'Sem descrição'))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #CCCCCC; font-size: 14px; line-height: 1.4;")
        content_layout.addWidget(desc)
        
        content_layout.addSpacing(20)
        
        # Ações
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        # Botão Download
        download_btn = QPushButton("BAIXAR AGORA")
        download_btn.setFixedSize(200, 50)
        download_btn.setCursor(Qt.PointingHandCursor)
        
        if disponivel:
            download_btn.setEnabled(True)
            download_btn.setStyleSheet(Styles.details_download_btn)
            
            def safe_download_click():
                """Handler seguro para evitar múltiplos cliques"""
                download_btn.setEnabled(False)
                original_text = download_btn.text()
                download_btn.setText("REQ. DOWNLOAD...")
                
                # Executa a ação
                self.parent_app.start_download_from_api(game_id, details.get('nome', 'Jogo'))
                
                # Reabilita após delay de segurança (caso o usuário volte para esta tela ou algo falhe)
                QTimer.singleShot(3000, lambda: self._reset_download_button(download_btn, original_text))
                
            download_btn.clicked.connect(safe_download_click)
        else:
            download_btn.setText("INDISPONÍVEL")
            download_btn.setEnabled(False)
            download_btn.setStyleSheet(Styles.details_download_btn_disabled)
            
        # Botão Steam
        steam_btn = QPushButton("Ver na Steam")
        steam_btn.setFixedSize(140, 50)
        steam_btn.setCursor(Qt.PointingHandCursor)
        steam_btn.setStyleSheet(Styles.details_steam_btn)
        steam_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{game_id}"))
        )
        
        actions_layout.addWidget(download_btn)
        actions_layout.addWidget(steam_btn)
        actions_layout.addStretch()
        
        content_layout.addLayout(actions_layout)
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _reset_download_button(self, btn, original_text):
        """Reseta o estado do botão de download"""
        try:
            btn.setEnabled(True)
            btn.setText(original_text)
            btn.setStyleSheet(Styles.details_download_btn)
        except RuntimeError:
            # Botão já pode ter sido destruído se a tela mudou
            pass

