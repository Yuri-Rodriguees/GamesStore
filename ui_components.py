"""Componentes de UI reutilizáveis - Design Moderno e Minimalista"""
from PyQt5.QtCore import Qt, pyqtProperty, pyqtSignal, QPropertyAnimation, QRectF, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QColor, QPen, QPainter, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import (
    QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, 
    QWidget, QGraphicsDropShadowEffect, QSizePolicy
)


# =============================================================================
# PALETA DE CORES MODERNA
# =============================================================================
class Colors:
    """Cores do tema moderno"""
    PRIMARY = "#47D64E"  # Verde principal
    PRIMARY_DARK = "#3AAE42"
    PRIMARY_LIGHT = "#5CE36C"
    
    BG_DARK = "#0D0D0D"  # Fundo mais escuro
    BG_MEDIUM = "#141414"
    BG_LIGHT = "#1A1A1A"
    BG_CARD = "#1E1E1E"
    BG_HOVER = "#252525"
    
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "rgba(255, 255, 255, 0.7)"
    TEXT_MUTED = "rgba(255, 255, 255, 0.4)"
    
    BORDER = "rgba(255, 255, 255, 0.08)"
    BORDER_HOVER = "rgba(71, 214, 78, 0.3)"
    
    ERROR = "#FF4757"
    SUCCESS = "#47D64E"
    WARNING = "#FFA502"


class TitleBar(QFrame):
    """Barra de título moderna e minimalista"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_DARK};
                border: none;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)
        
        # Logo com ícone
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(8)
        
        self.lbl_title = QLabel("Games Store")
        self.lbl_title.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.lbl_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; letter-spacing: 0.5px;")
        
        logo_layout.addWidget(self.lbl_title)
        
        layout.addWidget(logo_container)
        layout.addStretch()
        
        # Botões de controle da janela
        btn_style = """
            QPushButton {{
                background: transparent;
                color: {text};
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
        """
        
        # Minimizar
        self.btn_minimize = QPushButton("─")
        self.btn_minimize.setFixedSize(36, 28)
        self.btn_minimize.setCursor(Qt.PointingHandCursor)
        self.btn_minimize.setStyleSheet(btn_style.format(
            text=Colors.TEXT_SECONDARY, 
            hover_bg="rgba(255, 255, 255, 0.1)"
        ))
        self.btn_minimize.clicked.connect(parent.showMinimized)
        self.btn_minimize.setFocusPolicy(Qt.NoFocus)
        
        # Fechar
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(36, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.6);
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #FF4757;
                color: white;
            }
        """)
        self.btn_close.clicked.connect(parent.close)
        self.btn_close.setFocusPolicy(Qt.NoFocus)
        
        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_close)


class CircularProgressBar(QWidget):
    """Barra de progresso circular moderna com design glassmorphism"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self._value = 0
        self._speed = 0.0
        self._downloaded = 0
        self._total = 0
        self.max_value = 100
        self.progress_width = 8
        self.progress_rounded_cap = True
        
        # Cores do gradiente
        self.progress_color_start = QColor(71, 214, 78)  # Verde claro
        self.progress_color_end = QColor(46, 204, 113)   # Verde escuro
        self.bg_color = QColor(30, 30, 30)
        self.text_color = QColor(255, 255, 255)
        
        # Fontes modernas
        self.font_percent = QFont("Segoe UI", 22, QFont.Bold)
        self.font_speed = QFont("Segoe UI", 9)
        
        # Sombra suave
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(30)
        self.shadow_effect.setXOffset(0)
        self.shadow_effect.setYOffset(0)
        self.shadow_effect.setColor(QColor(71, 214, 78, 80))
        self.setGraphicsEffect(self.shadow_effect)
    
    @pyqtProperty(int)
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value != self._value:
            self._value = max(0, min(value, self.max_value))
            self.update()
    
    def set_value(self, value):
        self.value = value
    
    def set_speed(self, speed):
        self._speed = speed
        self.update()
    
    def set_downloaded(self, downloaded, total):
        self._downloaded = downloaded
        self._total = total
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        side = min(self.width(), self.height())
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Fundo circular com efeito glassmorphism
        bg_rect = QRectF(
            center_x - side/2 + 4, 
            center_y - side/2 + 4, 
            side - 8, side - 8
        )
        
        # Gradiente do fundo
        bg_gradient = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
        bg_gradient.setColorAt(0, QColor(35, 35, 35))
        bg_gradient.setColorAt(1, QColor(25, 25, 25))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_gradient)
        painter.drawEllipse(bg_rect)
        
        # Trilha do progresso (fundo)
        track_rect = bg_rect.adjusted(
            self.progress_width, self.progress_width,
            -self.progress_width, -self.progress_width
        )
        painter.setPen(QPen(QColor(50, 50, 50), self.progress_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(track_rect)
        
        # Progresso com gradiente
        if self._value > 0:
            progress_gradient = QLinearGradient(track_rect.topLeft(), track_rect.bottomRight())
            progress_gradient.setColorAt(0, self.progress_color_start)
            progress_gradient.setColorAt(1, self.progress_color_end)
            
            pen = QPen(progress_gradient, self.progress_width)
            if self.progress_rounded_cap:
                pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            
            start_angle = 90 * 16
            span_angle = -int(self._value * 3.6 * 16)
            painter.drawArc(track_rect, start_angle, span_angle)
        
        # Texto - Porcentagem (centralizado)
        painter.setFont(self.font_percent)
        painter.setPen(self.text_color)
        percent_text = f"{self._value}%"
        percent_rect = QRectF(0, side * 0.35, side, side * 0.25)
        painter.drawText(percent_rect, Qt.AlignCenter, percent_text)
        
        # Texto - Velocidade
        if self._speed > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(150, 150, 150))
            speed_rect = QRectF(0, side * 0.58, side, side * 0.12)
            painter.drawText(speed_rect, Qt.AlignCenter, f"{self._speed:.1f} MB/s")
        
        # Texto - Tamanho baixado
        if self._total > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(120, 120, 120))
            size_rect = QRectF(0, side * 0.70, side, side * 0.12)
            size_text = f"{self._downloaded}/{self._total} MB"
            painter.drawText(size_rect, Qt.AlignCenter, size_text)


class ModernButton(QPushButton):
    """Botão moderno com efeitos de hover e animações"""
    
    def __init__(self, text, primary=True, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        
        if primary:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 {Colors.PRIMARY},
                        stop:1 {Colors.PRIMARY_LIGHT}
                    );
                    color: {Colors.BG_DARK};
                    border: none;
                    border-radius: 10px;
                    padding: 12px 28px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 {Colors.PRIMARY_LIGHT},
                        stop:1 {Colors.PRIMARY}
                    );
                }}
                QPushButton:pressed {{
                    background: {Colors.PRIMARY_DARK};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Colors.TEXT_PRIMARY};
                    border: 2px solid {Colors.BORDER};
                    border-radius: 10px;
                    padding: 12px 28px;
                }}
                QPushButton:hover {{
                    border-color: {Colors.PRIMARY};
                    color: {Colors.PRIMARY};
                }}
            """)
        
        # Sombra suave
        if primary:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(71, 214, 78, 60))
            self.setGraphicsEffect(shadow)


class GameCard(QFrame):
    """Card de jogo moderno com efeitos de hover elegantes"""
    clicked = pyqtSignal(str, str)  # game_id, game_name
    
    def __init__(self, game_name, game_id, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.game_id = game_id
        
        self.setFixedSize(180, 280)
        self.setCursor(Qt.PointingHandCursor)
        
        self._setup_style()
        self._setup_ui()
        
        # Sombra suave
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)
    
    def _setup_style(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_CARD};
                border-radius: 16px;
                border: 1px solid {Colors.BORDER};
            }}
            QFrame:hover {{
                background: {Colors.BG_HOVER};
                border-color: {Colors.BORDER_HOVER};
            }}
        """)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(0)
        
        # Container da imagem
        self.image_container = QFrame()
        self.image_container.setFixedSize(164, 200)
        self.image_container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a2518,
                    stop:1 #0f1a0d
                );
                border-radius: 12px;
            }}
        """)
        
        # Imagem/Poster
        self.image_label = QLabel(self.image_container)
        self.image_label.setFixedSize(164, 200)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("🎮")
        self.image_label.setStyleSheet(f"""
            QLabel {{
                font-size: 48px;
                color: {Colors.PRIMARY};
                background: transparent;
                border-radius: 12px;
            }}
        """)
        
        # Nome do jogo
        self.name_label = QLabel(self.game_name)
        self.name_label.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(52)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                padding: 8px 4px 0px 4px;
                background: transparent;
            }}
        """)
        
        layout.addWidget(self.image_container)
        layout.addWidget(self.name_label)
    
    def set_image(self, pixmap):
        """Define a imagem do card"""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(164, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.image_label.setStyleSheet("background: transparent; border-radius: 12px;")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.game_id, self.game_name)


class SidebarButton(QPushButton):
    """Botão da sidebar com indicador de ativo"""
    
    def __init__(self, icon, text, parent=None):
        super().__init__(f"  {icon}  {text}", parent)
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(48)
        self.setFont(QFont("Segoe UI", 11))
        self._update_style()
    
    def set_active(self, active):
        self._active = active
        self._update_style()
    
    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(71, 214, 78, 0.2),
                        stop:1 transparent
                    );
                    color: {Colors.PRIMARY};
                    border: none;
                    border-left: 3px solid {Colors.PRIMARY};
                    border-radius: 0px;
                    text-align: left;
                    padding-left: 16px;
                    font-weight: 600;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Colors.TEXT_SECONDARY};
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    text-align: left;
                    padding-left: 16px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.05);
                    color: {Colors.TEXT_PRIMARY};
                }}
            """)
