"""
Workers de busca - SearchWorker, SearchWorkerSignals
"""
import json

import requests

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot as Slot


class SearchWorkerSignals(QObject):
    """Sinais para o worker de busca"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)


class SearchWorker(QRunnable):
    """Worker de busca"""
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = SearchWorkerSignals()
    
    @Slot()
    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            
            if not response.text or len(response.text.strip()) == 0:
                self.signals.error.emit("Resposta vazia da API")
                return
            
            if 'json' not in response.headers.get('content-type', ''):
                self.signals.error.emit("Resposta inválida (não é JSON)")
                return
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                self.signals.error.emit(f"Erro ao decodificar resposta: {e}")
                return
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                self.signals.finished.emit(jogos)
            else:
                error_msg = data.get('message', 'Erro desconhecido')
                self.signals.error.emit(error_msg)
                
        except requests.exceptions.Timeout:
            self.signals.error.emit("Tempo esgotado")
        except requests.exceptions.ConnectionError:
            self.signals.error.emit("Erro de conexão")
        except Exception as e:
            self.signals.error.emit(str(e))
