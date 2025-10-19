import os
import rc
import sys
import json
import math
import time
import xcore
import winreg
import base64
import psutil
import hashlib
import requests
import keyboard
import winsound
import pyperclip
import threading
import subprocess
from datax import Styles
from datetime import datetime, date
from PyQt5.QtGui import QMovie, QPainter, QLinearGradient, QColor, QPen, QIcon, QBrush, QPainterPath
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtWidgets import QMainWindow, QLabel, QFrame, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QRunnable, QThreadPool, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QPointF


class LoginWorkerSignals(QObject):
    success = pyqtSignal(str)
    error   = pyqtSignal(str)
    finished= pyqtSignal()


class LoadingScreen(QWidget):
    error_signal = pyqtSignal(str) 

    def __init__(self, validity: str, parent_window=None):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))
        self.loading_movie = QMovie(":/imgs/load.gif")
        
        self.loading_movie.start()
        gif_size = self.loading_movie.frameRect().size()
        self.setFixedSize(gif_size.width() + 40, gif_size.height() + 100)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.main_frame = QWidget()
        self.main_frame.setStyleSheet("""
            background-color: rgb(41, 39, 39);
            border-radius: 15px;
        """)
        self.layout.addWidget(self.main_frame)
        self.frame_layout = QVBoxLayout(self.main_frame)
        self.frame_layout.setContentsMargins(20, 20, 20, 20)
        self.frame_layout.setSpacing(20)

        self.loading_label = QLabel()
        self.loading_label.setMovie(self.loading_movie)
        self.loading_label.setFixedSize(gif_size)
        self.loading_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.loading_label.setAlignment(Qt.AlignCenter)

        self.loading_phrases = ["Carregando...", "Verificando...", "Iniciando...", "Conectando..."]
        self.current_phrase_index = 0

        self.text_label = QLabel(self.loading_phrases[self.current_phrase_index])
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        
        self.frame_layout.addStretch()
        self.frame_layout.addWidget(self.loading_label)
        self.frame_layout.addWidget(self.text_label)
        self.frame_layout.addStretch()
        
        self.text_timer = QTimer()
        self.text_timer.timeout.connect(self.update_loading_text)
        self.text_timer.start(500)
        self.parent_window_to_close = parent_window
        self.setup_license_info(validity)

    def setup_license_info(self, validity):
        if not validity:
            self.handle_invalid_date()
            return
            
        self.validity = validity.strip()

        if self.validity == "permanente":
            self.is_vitalicia = True
            QTimer.singleShot(1000, self.start_main_software)
        else:
            self.is_vitalicia = False
            try:
                self.expiry_date = datetime.fromisoformat(self.validity).date()
                today = date.today()
                
                if self.expiry_date < today:
                    self.handle_expired_key()
                else:
                    QTimer.singleShot(1000, self.start_main_software)
                    
            except (ValueError, TypeError) as e:
                self.handle_invalid_date()

    def handle_invalid_date(self):
        self.text_label.setText("Formato de data inválido!")
        self.text_label.setStyleSheet("""
            QLabel {
                color: red;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        QTimer.singleShot(3000, lambda: sys.exit(1))

    def handle_expired_key(self):
        if hasattr(self, 'text_timer'):
            self.text_timer.stop()
            
        self.text_label.setText("Chave expirada!")
        self.text_label.setStyleSheet("""
            QLabel {
                color: red;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        
        QTimer.singleShot(3200, self.cleanup_and_exit)

    def cleanup_and_exit(self):
        cleanup_thread = threading.Thread(target=self.perform_cleanup)
        cleanup_thread.start()
        
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(lambda: self.check_cleanup_thread(cleanup_thread))
        self.cleanup_timer.start(500)

    def check_cleanup_thread(self, thread):
        if not thread.is_alive():
            self.cleanup_timer.stop()
            sys.exit(1)

    def perform_cleanup(self):
        try:
            steam_path = self.get_steam_directory()
            if steam_path:
                self.close_steam_processes()
                
                max_attempts = 3
                for attempt in range(max_attempts):
                    success = self.remove_steam_files(steam_path)
                    if success:
                        break
                    time.sleep(2)
        except Exception as e:
            self.error_signal.emit(f"[ERRO] Falha durante a limpeza: {e}")

    def remove_steam_files(self, steam_path):
        required_files = [
            ".cef-dev-tools-size.vdf",
            "hid.dll"
        ]
        
        all_removed = True
        for filename in required_files:
            file_path = os.path.join(steam_path, filename)
            if not self.try_remove_file(file_path):
                all_removed = False
                
        return all_removed

    def get_steam_directory(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                return steam_path.replace("/", "\\")
        except Exception as e:
            self.error_signal.emit(f"[ERRO] Falha ao obter diretório do Steam: {e}")
            return None

    def try_remove_file(self, file_path):
        if not os.path.exists(file_path):
            return True

        try:
            os.remove(file_path)
            return True
        except PermissionError as e:
            if e.winerror == 32:
                return False
            self.error_signal.emit(f"[ERRO] Permissão negada ao remover {file_path}: {e}")
            return False
        except Exception as e:
            self.error_signal.emit(f"[ERRO] Falha ao remover {file_path}: {e}")
            return False

    def close_steam_processes(self):
        self.stop_steam_services()

        steam_process_names = ["steam.exe", "steamwebhelper.exe", "steamservice.exe", "gameoverlayui.exe"]
        closed_processes = False

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower() if proc.info['name'] else ""
                if any(steam_name in name for steam_name in steam_process_names):
                    parent = psutil.Process(proc.info['pid'])
                    children = parent.children(recursive=True)

                    for child in children:
                        try:
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    try:
                        parent.terminate()
                        parent.wait(timeout=5)
                        closed_processes = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    except psutil.TimeoutExpired:
                        try:
                            parent.kill()
                        except:
                            pass

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                self.error_signal.emit(f"[ERRO] Falha ao encerrar processo Steam: {e}")

        return closed_processes

    def stop_steam_services(self):
        steam_services = ["Steam Client Service", "Steam Installer Service"]
        for service in steam_services:
            try:
                subprocess.run(
                    ["sc", "stop", service],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(1)
            except subprocess.CalledProcessError as e:
                self.error_signal.emit(f"[AVISO] Falha ao parar serviço {service}: {e.stderr.decode().strip()}")
            except Exception as e:
                self.error_signal.emit(f"[ERRO] Falha ao parar serviço {service}: {e}")

    def update_loading_text(self):
        if not self.is_vitalicia:
            today = date.today()
            if hasattr(self, 'expiry_date') and self.expiry_date < today:
                self.handle_expired_key()
                return

        self.current_phrase_index = (self.current_phrase_index + 1) % len(self.loading_phrases)
        self.text_label.setText(self.loading_phrases[self.current_phrase_index])
    
    def start_main_software(self):
        try:
            self.main_app = xcore.start_software()
            if self.parent_window_to_close:
                self.parent_window_to_close.close()
            self.close()
        except Exception as e:
            print(f"ERRO CRÍTICO AO INICIAR SOFTWARE: {e}")
            if self.parent_window_to_close:
                self.parent_window_to_close.show()
                self.parent_window_to_close.login_error(f"Falha ao iniciar: {e}")
            self.close()


class LoginWorker(QRunnable):
    """Worker para autenticação com validação de HWID"""
    def __init__(self, username, password, key_extract, parent):
        super().__init__()
        self.username = username
        self.password = password
        self.hwid = key_extract
        self.parent = parent
        self.signals = LoginWorkerSignals()

    def run(self):
        API_LOGIN_URL = 'https://gamestore.squareweb.app/api/login/desktop'

        try:
            print(f"[LOGIN] Autenticando usuário: {self.username}")
            print(f"[LOGIN] HWID: {self.hwid}")
            
            payload = {
                'email_ou_usuario': self.username,
                'senha': self.password,
                'hwid': self.hwid 
            }

            response = requests.post(API_LOGIN_URL, json=payload, timeout=10)
            response_data = response.json()
            
            print(f"[LOGIN] Status Code: {response.status_code}")
            print(f"[LOGIN] Resposta: {response_data}")

            if response.status_code == 200:
                user_info = response_data.get('user')
                validity_from_api = user_info.get('vencimento') if user_info else None
                
                if validity_from_api:
                    validity_to_emit = validity_from_api
                else:
                    validity_to_emit = "permanente"

                print(f"[LOGIN] Login bem-sucedido! Validade: {validity_to_emit}")
                self.signals.success.emit(validity_to_emit)

            elif response.status_code == 400:
                error_message = response_data.get('message', 'Requisição inválida.')
                print(f"[LOGIN] Erro 400: {error_message}")
                self.signals.error.emit(f'Erro de requisição: {error_message}')
                
            elif response.status_code == 401:
                error_message = response_data.get('message', 'Email/Usuário ou senha inválidos.')
                print(f"[LOGIN] Erro 401: {error_message}")
                self.signals.error.emit(f'{error_message}')

            elif response.status_code == 403:
                error_message = response_data.get('message', 'HWID não corresponde ou acesso negado.')
                print(f"[LOGIN] Erro 403: {error_message}")
                self.signals.error.emit(f'{error_message}')
                
            elif response.status_code == 500:
                error_message = response_data.get('message', 'Erro interno do servidor.')
                print(f"[LOGIN] Erro 500: {error_message}")
                self.signals.error.emit(f'Erro do servidor: {error_message}')
                
            else:
                error_message = response_data.get('message', 'Erro desconhecido')
                print(f"[LOGIN] Erro {response.status_code}: {error_message}")
                self.signals.error.emit(f'{error_message}')

        except requests.exceptions.Timeout:
            print("[LOGIN] Timeout: Servidor não respondeu")
            self.signals.error.emit('Timeout: Servidor não respondeu.')
            
        except requests.exceptions.ConnectionError:
            print("[LOGIN] Erro de conexão")
            self.signals.error.emit('Erro de conexão. Verifique sua internet.')
            
        except json.JSONDecodeError:
            print("[LOGIN] Resposta não é JSON")
            self.signals.error.emit('Resposta inválida do servidor.')
            
        except Exception as e:
            print(f"[LOGIN] Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(f'Erro: {e}')
            
        finally:
            self.signals.finished.emit()

class softwarerei(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(730, 550)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(Styles.main_window)
        self.setWindowIcon(QIcon(":/imgs/icon.ico"))

        self.thread_pool = QThreadPool()

        keyboard.add_hotkey('f1', self.generate_unique_code)

        self.pulse_angle = 0.0
        self.pulse_speed = 0.011
        self.corner_line_width = 4
        self.tail_length = 0.21
        self.gradient_color = QColor("#3EC26A")

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(6)

        self.logo = QFrame(self)
        self.logo.setGeometry(105, 55, 450, 181)
        self.logo.setFrameShape(QFrame.Shape.StyledPanel)
        self.logo.setFrameShadow(QFrame.Shadow.Raised)
        self.logo.setObjectName('logo')
        self.logo_gif = QLabel(self.logo)
        self.logo_gif.setGeometry(100, 0, 450, 170)
        gif_path = ':/imgs/banner.png'
        self.movie = QMovie(gif_path)
        self.logo_gif.setMovie(self.movie)
        self.movie.start()
        self.logo_gif.setObjectName('logo_gif')
        self.logo.setStyleSheet("border: none;")

        self.username_input = QLineEdit(self)
        self.username_input.setGeometry(225, 300, 280, 50)
        self.username_input.setStyleSheet(Styles.line_edit)
        self.username_input.setPlaceholderText("Usuário")

        self.password_input = QLineEdit(self)
        self.password_input.setGeometry(225, 370, 280, 50)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(Styles.line_edit)
        self.password_input.setPlaceholderText("Senha")

        self.login_button = QPushButton("Login", self)
        self.login_button.setGeometry(295, 445, 141, 50)
        self.login_button.setStyleSheet(Styles.button)
        self.login_button.clicked.connect(self.on_login_clicked)

        self.frame_error_2 = QFrame(self)
        self.frame_error_2.setMaximumSize(350, 350)
        self.frame_error_2.setGeometry(186, 246, 370, 35)
        self.frame_error_2.setStyleSheet(Styles.popup_error)
        self.frame_error_2.setFrameShape(QFrame.StyledPanel)
        self.frame_error_2.setFrameShadow(QFrame.Raised)
        self.frame_error_2.setObjectName('frame_error_2')
        self.frame_error_2.hide()

        self.pushButton_close_pupup_2 = QPushButton(self.frame_error_2)
        self.pushButton_close_pupup_2.setMaximumSize(20, 20)
        self.pushButton_close_pupup_2.setGeometry(320, 7, 20, 20)
        self.pushButton_close_pupup_2.setStyleSheet(Styles.close_button)
        self.pushButton_close_pupup_2.clicked.connect(lambda: self.frame_error_2.hide())

        self.label_error_2 = QLabel(self.frame_error_2)
        self.label_error_2.setStyleSheet('color: rgb(35, 35, 35); border: none;')
        self.label_error_2.setGeometry(10, 3, 300, 24)
        self.label_error_2.setAlignment(Qt.AlignCenter)
        self.label_error_2.setObjectName('label_error_2')
        
    def get_point_on_perimeter(self, progress, rect):
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        perimeter = 2 * (w + h)
        distance = progress * perimeter

        if distance < w:
            return (x + distance, y)
        distance -= w

        if distance < h:
            return (x + w, y + distance)
        distance -= h

        if distance < w:
            return (x + w - distance, y + h)
        distance -= w

        return (x, y + h - distance)

    def animate(self):
        self.pulse_angle += self.pulse_speed
        if self.pulse_angle > math.pi * 2:
            self.pulse_angle = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        animation_progress = self.pulse_angle / (math.pi * 2)
        end_progress = animation_progress
        start_progress = (animation_progress - self.tail_length) % 1.0

        path = QPainterPath()
        start_point = self.get_point_on_perimeter(start_progress, rect)
        path.moveTo(QPointF(start_point[0], start_point[1]))

        current_progress = start_progress
        num_steps = 100
        step = self.tail_length / num_steps

        for _ in range(num_steps + 1):
            current_progress = (current_progress + step) % 1.0
            point = self.get_point_on_perimeter(current_progress, rect)
            path.lineTo(QPointF(point[0], point[1]))
            if abs(current_progress - end_progress) < step / 2:
                break

        gradient = QLinearGradient(start_point[0], start_point[1], point[0], point[1])

        transparent_color = self.gradient_color.toRgb()
        transparent_color.setAlpha(0)
        gradient.setColorAt(0.0, transparent_color)
        gradient.setColorAt(0.5, self.gradient_color)
        gradient.setColorAt(1.0, self.gradient_color)

        pen = QPen(QBrush(gradient), self.corner_line_width, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        painter.drawPath(path)

        super().paintEvent(event)

    def key(self):
        """Gera HWID único do computador"""
        def get_disk_serial():
            try:
                result = subprocess.check_output("wmic diskdrive get SerialNumber", shell=True)
                serials = result.decode().split("\n")
                serials = [s.strip() for s in serials if s.strip() and "SerialNumber" not in s]
                return serials[0] if serials else "NO_DISK"
            except Exception:
                return "UNKNOWN_DISK"

        def get_mac_address():
            try:
                for iface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if hasattr(psutil, "AF_LINK"):
                            if addr.family == psutil.AF_LINK and addr.address != "00:00:00:00:00:00":
                                return addr.address.replace(":", "")
                        else:
                            if addr.family == 17 and addr.address != "00:00:00:00:00:00":
                                return addr.address.replace(":", "")
            except Exception:
                return "UNKNOWN_MAC"
            return "UNKNOWN_MAC"

        disk = get_disk_serial()
        mac = get_mac_address()
        raw = f"{disk}_{mac}"
        self.key_extract = hashlib.sha256(raw.encode()).hexdigest().upper()[:24]

    def generate_unique_code(self, checked=False):
        """Copia HWID para clipboard (F1)"""
        self.key()
        unique_key = self.key_extract
        pyperclip.copy(unique_key)

        self.label_error_2.setText(f"HWID copiada: {unique_key}")
        self.frame_error_2.setStyleSheet(Styles.popup_ok)
        self.frame_error_2.show()

    def on_login_clicked(self, checked=False):
        """Executa login com validação de HWID"""
        self.login_button.setEnabled(False)
        self.login_button.setText("Autenticando...")
        
        # Gerar HWID
        self.key()
        
        campo_user = self.username_input.text().strip()
        campo_senha = self.password_input.text().strip()
        
        # Validações básicas
        if not campo_user or not campo_senha:
            self.show_message("Preencha todos os campos", success=False)
            self.login_button.setEnabled(True)
            self.login_button.setText("Login")
            return
        
        # Criar worker com HWID
        worker = LoginWorker(
            username=campo_user,
            password=campo_senha,
            key_extract=self.key_extract,  # ✅ HWID enviado
            parent=self
        )
        
        worker.signals.success.connect(self.login_success)
        worker.signals.error.connect(self.login_error)
        worker.signals.finished.connect(self.login_finished)
        
        self.thread_pool.start(worker)

    def login_success(self, validity: str):
        self.show_message("Logado com sucesso!", success=True)
        self.username_input.setStyleSheet(Styles.line_edit_ok)
        self.password_input.setStyleSheet(Styles.line_edit_ok)

        self.loading_screen = LoadingScreen(validity, parent_window=self)
        self.loading_screen.show()

        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.loading_screen.width()) // 2
        y = (screen_geometry.height() - self.loading_screen.height()) // 2
        self.loading_screen.move(x, y)
        
    def close_and_start(self):
        if hasattr(self, 'loading_screen'):
            self.loading_screen.close()
        self.close()

    def login_error(self, message):
        self.show_message(message, success=False)
        self.username_input.setStyleSheet(Styles.line_edit_error)
        self.password_input.setStyleSheet(Styles.line_edit_error)

    def login_finished(self):
        self.login_button.setEnabled(True)
        self.login_button.setText("Login")
    
    def animate_close(self):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def show_message(self, message, success=False):
        self.frame_error_2.setStyleSheet(Styles.popup_ok if success else Styles.popup_error)
        self.label_error_2.setText(message)
        self.frame_error_2.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
            
    def notific(self):
        arquivo_audio = 'assets/Images/notic.wav'
        winsound.PlaySound(arquivo_audio, winsound.SND_ASYNC)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos'):
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
