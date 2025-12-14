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
            print(f"[SearchWorker] Requisitando: {self.url}")
            
            response = requests.get(self.url, timeout=10)
            
            print(f"[SearchWorker] Status: {response.status_code}")
            print(f"[SearchWorker] Content-Type: {response.headers.get('content-type')}")
            print(f"[SearchWorker] Response length: {len(response.text)}")
            
            if not response.text or len(response.text.strip()) == 0:
                self.signals.error.emit("Resposta vazia da API")
                return
            
            if 'json' not in response.headers.get('content-type', ''):
                print(f"[SearchWorker] Resposta não é JSON: {response.text[:200]}")
                self.signals.error.emit("Resposta inválida (não é JSON)")
                return
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"[SearchWorker] Erro JSON: {e}")
                print(f"[SearchWorker] Response: {response.text[:500]}")
                self.signals.error.emit(f"Erro ao decodificar resposta: {e}")
                return
            
            if data.get('status') == 'success':
                jogos = data.get('jogos', [])
                print(f"[SearchWorker] ✅ {len(jogos)} jogos encontrados")
                self.signals.finished.emit(jogos)
            else:
                error_msg = data.get('message', 'Erro desconhecido')
                print(f"[SearchWorker] ❌ Erro: {error_msg}")
                self.signals.error.emit(error_msg)
                
        except requests.exceptions.Timeout:
            print(f"[SearchWorker] ❌ Timeout")
            self.signals.error.emit("Tempo esgotado")
        except requests.exceptions.ConnectionError:
            print(f"[SearchWorker] ❌ Connection error")
            self.signals.error.emit("Erro de conexão")
        except Exception as e:
            print(f"[SearchWorker] ❌ Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(str(e))
