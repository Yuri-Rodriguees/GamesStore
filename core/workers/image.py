"""
Workers de carregamento de imagens - ImageLoader, ImageLoaderSignals
Otimizado para carregamento rapido com cache e fallbacks
"""
import requests
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import Qt, QObject, QRunnable, pyqtSignal, pyqtSlot as Slot
from PyQt5.QtGui import QPixmap


# Pool de conexoes para reutilizacao
_session = None

def get_session():
    """Retorna sessao HTTP reutilizavel para melhor performance"""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=1
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    return _session


class ImageLoaderSignals(QObject):
    """Sinais para carregamento de imagens"""
    finished = pyqtSignal(QPixmap)
    error = pyqtSignal()


class ImageLoader(QRunnable):
    """Worker otimizado para carregar imagens com cache e multiplos fallbacks"""
    def __init__(self, urls, cache_key=None, max_size=(300, 300), parent_cache=None):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.cache_key = cache_key
        self.max_size = max_size
        self.parent_cache = parent_cache
        self.signals = ImageLoaderSignals()
    
    @Slot()
    def run(self):
        """Tenta carregar de multiplas URLs com cache"""
        # Verificar cache primeiro
        if self.cache_key and self.parent_cache and self.cache_key in self.parent_cache:
            cached_pixmap = self.parent_cache[self.cache_key]
            if cached_pixmap and not cached_pixmap.isNull():
                self.signals.finished.emit(cached_pixmap)
                return
        
        session = get_session()
        
        # Tentar carregar de URLs
        for url in self.urls:
            try:
                # Timeout reduzido para performance
                response = session.get(url, timeout=5, stream=True)
                
                if response.status_code == 200:
                    content = response.content
                    
                    pixmap = QPixmap()
                    if pixmap.loadFromData(content):
                        # Redimensionar se necessario
                        if self.max_size and (pixmap.width() > self.max_size[0] or pixmap.height() > self.max_size[1]):
                            pixmap = pixmap.scaled(
                                self.max_size[0], self.max_size[1],
                                Qt.KeepAspectRatio,
                                Qt.FastTransformation  # Mais rapido que SmoothTransformation
                            )
                        
                        # Salvar no cache
                        if self.cache_key and self.parent_cache is not None:
                            # Limitar tamanho do cache
                            if '__parent_app' in self.parent_cache:
                                parent_app = self.parent_cache['__parent_app']
                                max_size = getattr(parent_app, '_max_cache_size', 150)
                                image_keys = [k for k in self.parent_cache.keys() if k != '__parent_app']
                                if len(image_keys) >= max_size:
                                    # Remover itens mais antigos
                                    for key in list(image_keys)[:10]:
                                        if key in self.parent_cache:
                                            del self.parent_cache[key]
                            
                            self.parent_cache[self.cache_key] = pixmap
                        
                        self.signals.finished.emit(pixmap)
                        return
                    
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException:
                continue
            except Exception:
                continue
        
        self.signals.error.emit()
