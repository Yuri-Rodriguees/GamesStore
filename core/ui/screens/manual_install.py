"""
Tela de instalação manual - ManualInstallScreen
"""
import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel,
    QFileDialog, QMessageBox
)

from utils import log_message


class ManualInstallScreen(QWidget):
    """Tela de instalação manual de jogo - Versão simplificada"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent_app = parent
        self.selected_file_path = None
        
        # Layout principal simples
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        
        # Botão voltar
        back_btn = QPushButton("← Voltar")
        back_btn.setFixedSize(100, 40)
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
        def go_back():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
            except Exception as e:
                log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao voltar: {e}")
        
        back_btn.clicked.connect(go_back)
        layout.addWidget(back_btn)
        
        # Título
        title = QLabel("📥 Instalação Manual de Jogo")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Instruções
        instructions = QLabel(
            "Selecione um arquivo .ZIP ou .RAR no formato:\n"
            "Nome do Jogo (ID).zip\n\n"
            "Exemplo: GTA V (271590).rar"
        )
        instructions.setFont(QFont("Arial", 13))
        instructions.setStyleSheet("color: rgba(255, 255, 255, 0.7); padding: 20px;")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Frame de seleção de arquivo
        file_frame = QFrame()
        file_frame.setFixedHeight(120)
        file_frame.setStyleSheet("""
            QFrame {
                background: #232323;
                border-radius: 12px;
                border: 2px solid #333;
            }
        """)
        
        file_layout = QVBoxLayout(file_frame)
        file_layout.setAlignment(Qt.AlignCenter)
        
        self.file_label = QLabel("📁 Nenhum arquivo selecionado")
        self.file_label.setFont(QFont("Arial", 12))
        self.file_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setWordWrap(True)
        
        file_layout.addWidget(self.file_label)
        layout.addWidget(file_frame)
        
        # Botão de seleção
        btn_select = QPushButton("🔍 Selecionar Arquivo")
        btn_select.setFixedHeight(50)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 2px solid #47D64E;
                border-radius: 25px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #333333;
                border-color: #5ce36c;
            }
        """)
        btn_select.clicked.connect(self.select_file)
        layout.addWidget(btn_select)
        
        layout.addStretch()
        
        # Botões de ação
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedSize(150, 50)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: 25px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #333;
            }
        """)
        def cancel_action():
            try:
                if self.parent_app and hasattr(self.parent_app, 'pages'):
                    self.parent_app.pages.setCurrentIndex(1)
            except Exception as e:
                log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao cancelar: {e}")
        
        btn_cancel.clicked.connect(cancel_action)
        
        btn_install = QPushButton("🚀 Instalar")
        btn_install.setFixedSize(150, 50)
        btn_install.setCursor(Qt.PointingHandCursor)
        btn_install.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #47D64E,
                    stop:1 #5ce36c
                );
                color: #1F1F1F;
                border: none;
                border-radius: 25px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5ce36c,
                    stop:1 #6ff57d
                );
            }
            QPushButton:disabled {
                background: #333;
                color: #666;
            }
        """)
        btn_install.clicked.connect(self.start_install)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_cancel)
        buttons_layout.addWidget(btn_install)
        
        layout.addLayout(buttons_layout)
    
    def select_file(self, checked=False):
        """Abre dialog para selecionar arquivo"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar Arquivo de Jogo",
                os.path.expanduser("~"),
                "Arquivos de Jogo (*.zip *.rar);;Todos os Arquivos (*.*)",
                options=QFileDialog.DontUseNativeDialog
            )
            
            if file_path:
                self.selected_file_path = file_path
                filename = os.path.basename(file_path)
                if hasattr(self, 'file_label') and self.file_label:
                    self.file_label.setText(f"✅ {filename}")
                    self.file_label.setStyleSheet("color: #47D64E;")
                    
                    # Validar formato
                    match = re.match(r"^(.+?)\s*\((\d+)\)\.(zip|rar)$", filename, re.IGNORECASE)
                    if not match:
                        self.file_label.setText(f"⚠️ {filename}\n(Formato inválido)")
                        self.file_label.setStyleSheet("color: #ff9500;")
        except Exception as e:
            log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao selecionar arquivo: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao selecionar arquivo:\n{str(e)}")
    
    def start_install(self, checked=False):
        """Inicia instalação manual"""
        try:
            if not self.selected_file_path:
                QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro!")
                return
            
            # Verificar se parent_app existe e tem os métodos necessários
            if not self.parent_app:
                QMessageBox.critical(self, "Erro", "Aplicação principal não disponível")
                return
            
            # Voltar para tela de jogos
            if hasattr(self.parent_app, 'pages'):
                self.parent_app.pages.setCurrentIndex(1)
            
            # Iniciar instalação
            if hasattr(self.parent_app, 'install_manual_game'):
                self.parent_app.install_manual_game(self.selected_file_path)
            else:
                QMessageBox.critical(self, "Erro", "Método de instalação não disponível")
        except Exception as e:
            log_message(f"[MANUAL_INSTALL_SCREEN] Erro ao iniciar instalação: {e}", include_traceback=True)
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar instalação:\n{str(e)}")
