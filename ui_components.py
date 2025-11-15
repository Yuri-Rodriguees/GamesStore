"""Componentes de UI reutilizáveis"""
from PyQt5.QtCore import Qt, pyqtProperty, pyqtSignal, QPropertyAnimation, QRectF
from PyQt5.QtGui import QFont, QIcon, QColor, QPen, QPainter, QPainterPath
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QHBoxLayout, QWidget, QGraphicsDropShadowEffect


class TitleBar(QFrame):
    """Barra de título personalizada para janelas sem borda"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: #222; padding: 5px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        self.setFixedHeight(40)
        
        title_layout = QHBoxLayout(self)
        title_layout.setContentsMargins(10, 0, 10, 0)
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        
        self.lbl_title = QLabel("Games Store")
        self.lbl_title.setFont(QFont("Arial", 10))
        self.lbl_title.setStyleSheet("color: white;")
        self.lbl_title.setAlignment(Qt.AlignLeft)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet("background: none; color: white; font-size: 14px; border: none;")
        self.btn_close.clicked.connect(parent.close)
        self.btn_close.setFocusPolicy(Qt.NoFocus)
        
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.btn_close)


class CircularProgressBar(QWidget):
    """Barra de progresso circular moderna"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self._value = 0
        self._speed = 0.0
        self._downloaded = 0
        self._total = 0
        self.max_value = 100
        self.progress_width = 10
        self.progress_rounded_cap = True
        self.progress_color = QColor(75, 215, 100)
        self.text_color = QColor(255, 255, 255)
        self.font_percent = QFont("Arial", 14, QFont.Bold)
        self.font_speed = QFont("Arial", 9)
        
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(20)
        self.shadow_effect.setXOffset(0)
        self.shadow_effect.setYOffset(0)
        self.shadow_effect.setColor(QColor(75, 215, 100, 150))
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
        """Define o progresso (0-100)"""
        self.value = value
    
    def set_speed(self, speed):
        """Define a velocidade em MB/s"""
        self._speed = speed
        self.update()
    
    def set_downloaded(self, downloaded, total):
        """Define bytes baixados e total"""
        self._downloaded = downloaded
        self._total = total
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        side = min(self.width(), self.height())
        rect = QRectF(0, 0, side, side)
        
        # Fundo
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawEllipse(rect)
        
        # Progresso
        pen = QPen(self.progress_color, self.progress_width)
        if self.progress_rounded_cap:
            pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        start_angle = 90 * 16
        span_angle = -int(self._value * 3.6 * 16)
        
        margin = self.progress_width / 2
        arc_rect = QRectF(
            margin, margin,
            side - self.progress_width,
            side - self.progress_width
        )
        painter.drawArc(arc_rect, start_angle, span_angle)
        
        # Texto - Porcentagem
        painter.setFont(self.font_percent)
        painter.setPen(self.text_color)
        percent_rect = QRectF(0, side * 0.35, side, side * 0.2)
        painter.drawText(percent_rect, Qt.AlignCenter, f"{self._value}%")
        
        # Texto - Velocidade
        if self._speed > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(200, 200, 200))
            speed_rect = QRectF(0, side * 0.55, side, side * 0.15)
            painter.drawText(speed_rect, Qt.AlignCenter, f"{self._speed:.1f} MB/s")
        
        # Texto - Tamanho
        if self._total > 0:
            painter.setFont(self.font_speed)
            painter.setPen(QColor(180, 180, 180))
            size_rect = QRectF(0, side * 0.68, side, side * 0.15)
            painter.drawText(size_rect, Qt.AlignCenter, f"{self._downloaded}/{self._total} MB")

