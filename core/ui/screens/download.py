"""
Tela de download - DownloadScreen
"""
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
)

from ui_components import CircularProgressBar
from utils import log_message
from core.workers.download import DownloadWorker


class DownloadScreen(QWidget):
    """Tela profissional de download com barra circular moderna"""
    download_finished = pyqtSignal(str, str)  # (message, game_id)
    
    def __init__(self, parent, game_id, game_name, download_url, steam_path):
        super().__init__(parent)
        self.parent_app = parent
        self.game_id = game_id
        self.game_name = game_name
        self._is_closing = False
        
        # Estilo da tela
        self.setStyleSheet("""
            QWidget {
                background-color: #1F1F1F;
            }
            QLabel {
                color: #E0E0E0;
            }
        """)
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignCenter)
        
        # Título do jogo
        title = QLabel(f"Baixando {game_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)
        
        # Barra de progresso circular
        self.progress_bar = CircularProgressBar(self)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        # Status
        self.status_label = QLabel("Preparando download...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.status_label)
        
        # Espaçamento
        layout.addStretch()
        
        # Botão Voltar (só aparece após download concluir)
        self.back_btn = QPushButton("← Voltar")
        self.back_btn.setFixedHeight(45)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 30px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-color: #47D64E;
            }
        """)
        self.back_btn.hide()  # Inicialmente oculto
        self.back_btn.clicked.connect(self.go_back)
        layout.addWidget(self.back_btn, alignment=Qt.AlignCenter)
        
        # Inicia worker
        self.worker = DownloadWorker(game_id, download_url, game_name, steam_path)
        self.worker.signals.progress.connect(self.progress_bar.setValue)
        self.worker.signals.status.connect(self.status_label.setText)
        self.worker.signals.success.connect(self.on_download_success)
        self.worker.signals.error.connect(self.on_download_error)
        
        parent.thread_pool.start(self.worker)
    
    def on_download_success(self, message, filepath, game_id):
        """Callback de sucesso - atualiza UI e pergunta sobre Steam"""
        log_message(f"[DOWNLOAD SCREEN] Download concluído - game_id={game_id}")
        
        if self._is_closing:
            return
        
        try:
            self._is_closing = True
            
            # Atualizar UI
            self.status_label.setText("✅ Download concluído com sucesso!")
            self.status_label.setStyleSheet("color: #47D64E; font-weight: bold;")
            self.progress_bar.setValue(100)
            
            # Mostrar botão voltar
            self.back_btn.show()
            
            # Desconectar signals
            try:
                if hasattr(self, 'worker') and self.worker:
                    self.worker.signals.progress.disconnect()
                    self.worker.signals.status.disconnect()
                    self.worker.signals.success.disconnect()
                    self.worker.signals.error.disconnect()
            except:
                pass
            
            # Emitir signal de download finalizado
            try:
                self.download_finished.emit(message, game_id)
            except:
                pass
            
            # Perguntar sobre reiniciar Steam após um pequeno delay
            QTimer.singleShot(500, lambda: self.ask_restart_steam())
            
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao processar sucesso: {e}", include_traceback=True)
    
    def ask_restart_steam(self):
        """Pergunta se deseja reiniciar a Steam"""
        try:
            log_message("[DOWNLOAD SCREEN] Perguntando sobre reiniciar Steam...")
            
            if self.parent_app and hasattr(self.parent_app, 'ask_restart_steam'):
                self.parent_app.ask_restart_steam()
            else:
                # Fallback: perguntar diretamente
                reply = QMessageBox.question(
                    self,
                    "Reiniciar Steam",
                    "O novo jogo foi instalado!\nDeseja reiniciar a Steam para aparecer na biblioteca?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    if self.parent_app and hasattr(self.parent_app, 'restart_steam'):
                        QTimer.singleShot(100, self.parent_app.restart_steam)
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao perguntar sobre Steam: {e}")
    
    def on_download_error(self, error_msg):
        """Callback de erro"""
        log_message(f"[DOWNLOAD SCREEN] Erro: {error_msg}")
        self.status_label.setText(f"❌ Erro: {error_msg}")
        self.status_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        self.back_btn.show()  # Mostrar botão voltar mesmo em caso de erro
        QMessageBox.critical(self, "Erro no Download", error_msg)
    
    def go_back(self):
        """Volta para a tela anterior"""
        try:
            log_message("[DOWNLOAD SCREEN] Voltando para tela anterior...")
            if self.parent_app:
                # Voltar para tela de jogos
                self.parent_app.pages.setCurrentIndex(1)  # tela_jogos
        except Exception as e:
            log_message(f"[DOWNLOAD SCREEN] Erro ao voltar: {e}")
