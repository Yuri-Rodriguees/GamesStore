"""
Overlays de UI - DownloadProgressOverlay, ManualInstallProgressOverlay, SpotlightOverlay
"""
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QPropertyAnimation, pyqtProperty, QThreadPool
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QLabel, QProgressBar, 
    QMessageBox, QGraphicsOpacityEffect
)

from ui_components import CircularProgressBar
from utils import log_message


class DownloadProgressOverlay(QDialog):
    """Dialog de progresso de download com barra circular"""
    def __init__(self, parent, game_name):
        super().__init__(parent)
        self.game_name = game_name
        self._is_closing = False
        
        # Configurar dialog
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 12px;
                border: 2px solid #47D64E;
            }
        """)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Título
        title = QLabel(f"Baixando {game_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        # Barra de progresso circular (da ui_components)
        self.progress_bar = CircularProgressBar(self)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        # Status
        self.status_label = QLabel("Preparando download...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def on_download_success(self, message, filepath, game_id):
        """Callback de sucesso - fecha o dialog"""
        if self._is_closing:
            return
        
        try:
            self._is_closing = True
            
            # Atualizar UI
            self.status_label.setText("✅ Download concluído com sucesso!")
            self.status_label.setStyleSheet("color: #47D64E; font-weight: bold;")
            self.progress_bar.set_value(100)
            
            # Desconectar signals
            try:
                if hasattr(self, 'worker') and self.worker:
                    self.worker.signals.progress.disconnect()
                    self.worker.signals.status.disconnect()
                    self.worker.signals.success.disconnect()
                    self.worker.signals.error.disconnect()
            except:
                pass
            
            # Fechar dialog após pequeno delay
            QTimer.singleShot(500, self.accept)
            
        except Exception as e:
            log_message(f"[DOWNLOAD_PROGRESS] Erro em on_download_success: {e}")
            self.accept()
    
    def on_download_error(self, error_msg):
        """Callback de erro"""
        log_message(f"[DOWNLOAD_PROGRESS] Erro: {error_msg}")
        self.status_label.setText(f"❌ Erro: {error_msg}")
        self.status_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        QTimer.singleShot(2000, self.reject)


class ManualInstallProgressOverlay(QDialog):
    """Overlay de progresso para instalação manual"""
    
    def __init__(self, parent, game_id, game_name, filepath, steam_path):
        super().__init__(parent)
        self.game_id = game_id
        self.game_name = game_name
        self.filepath = filepath
        self.steam_path = steam_path
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setFixedSize(500, 350)
        
        self.setup_ui()
        
        # Iniciar instalação
        QTimer.singleShot(100, self.start_installation)
    
    def setup_ui(self):
        """Configura interface do overlay"""
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                border-radius: 16px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        
        # Título
        title = QLabel(f"Instalando {self.game_name}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        
        # Status
        self.status_label = QLabel("Preparando instalação...")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(30)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #232323;
                border: 2px solid #333;
                border-radius: 15px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                border-radius: 13px;
            }
        """)
        self.progress_bar.setValue(0)
        
        # Detalhes
        self.details_label = QLabel(f"ID: {self.game_id}")
        self.details_label.setFont(QFont("Arial", 10))
        self.details_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        self.details_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.details_label)
    
    def start_installation(self):
        """Inicia processo de instalação"""
        from core.workers.install import ManualInstallWorker
        
        worker = ManualInstallWorker(
            self.game_id, 
            self.game_name, 
            self.filepath, 
            self.steam_path
        )
        
        worker.signals.progress.connect(self.update_progress)
        worker.signals.status.connect(self.update_status)
        worker.signals.success.connect(self.on_success)
        worker.signals.error.connect(self.on_error)
        
        QThreadPool.globalInstance().start(worker)
    
    def update_progress(self, value):
        """Atualiza barra de progresso"""
        self.progress_bar.setValue(value)
    
    def update_status(self, status):
        """Atualiza mensagem de status"""
        self.status_label.setText(status)
    
    def on_success(self, message):
        """Callback de sucesso"""
        self.accept()
        QMessageBox.information(self.parent(), "✅ Instalação Concluída", message)
        self.parent().load_installed_games()
        
        # Perguntar sobre reiniciar Steam
        QTimer.singleShot(500, self.parent().ask_restart_steam)
    
    def on_error(self, error_msg):
        """Callback de erro"""
        self.reject()
        QMessageBox.critical(self.parent(), "❌ Erro na Instalação", 
            f"Falha ao instalar o jogo:\n\n{error_msg}")


class SpotlightOverlay(QWidget):
    """Overlay moderno que destaca um widget específico com animação de foco"""
    
    def __init__(self, parent, target_widget):
        super().__init__(parent)
        self.parent = parent
        self.target_widget = target_widget
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setGeometry(parent.rect())

        # Efeito de opacidade geral
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity.setDuration(600)
        self.opacity.setStartValue(0.0)
        self.opacity.setEndValue(1.0)
        self.opacity.start()

        # Timer de duração e fade out automático
        QTimer.singleShot(2500, self.fade_out)

        self.pulse = 0  # controle de brilho pulsante
        self.pulse_anim = QPropertyAnimation(self, b"pulsing")
        self.pulse_anim.setDuration(1200)
        self.pulse_anim.setStartValue(0)
        self.pulse_anim.setEndValue(1)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.start()

        self.show()
        self.raise_()

    # Property usada para animar o brilho pulsante
    @pyqtProperty(float)
    def pulsing(self):
        return self.pulse

    @pulsing.setter
    def pulsing(self, value):
        self.pulse = value
        self.update()

    def fade_out(self):
        self.fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade.setDuration(700)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.deleteLater)
        self.fade.start()

    def paintEvent(self, event):
        if not self.target_widget:
            return
        
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        
        # Fundo escuro translúcido
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))
        
        # Calcular posição e tamanho do widget alvo
        widget_screen_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
        widget_local = self.mapFromGlobal(widget_screen_pos)
        target_rect = QRect(widget_local, self.target_widget.size())
        target_rect = target_rect.adjusted(-10, -10, 10, 10)
        
        # Criar caminho com "recorte" para o foco
        highlight_path = QPainterPath()
        highlight_path.addRect(self.rect())
        
        spot_path = QPainterPath()
        spot_path.addRoundedRect(QRectF(target_rect), 14, 14)
        highlight_path = highlight_path.subtracted(spot_path)
        
        # Desenhar "buraco" de foco
        painter.fillPath(highlight_path, QColor(0, 0, 0, 220))
        
        # Desenhar borda iluminada e suave pulsante
        pulse_strength = 80 + int(40 * abs(self.pulse - 0.5) * 2)
        glow_color = QColor(71, 214, 78, pulse_strength)
        
        glow_pen = QPen(glow_color, 3)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(target_rect), 14, 14)

        # Pequeno texto informativo ("Novo jogo instalado!") acima
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.setPen(QColor(255, 255, 255, 230))
        msg_rect = QRectF(target_rect.left(), target_rect.top() - 35, target_rect.width(), 25)
        painter.drawText(msg_rect, Qt.AlignCenter, "🎮 Novo jogo instalado!")
