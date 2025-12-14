"""
Workers de carregamento de imagens - ImageLoader, ImageLoaderSignals
"""
import requests

from PyQt5.QtCore import Qt, QObject, QRunnable, pyqtSignal, pyqtSlot as Slot
from PyQt5.QtGui import QPixmap


class ImageLoaderSignals(QObject):
    """Sinais para carregamento de imagens"""
    finished = pyqtSignal(QPixmap)
    error = pyqtSignal()


class ImageLoader(QRunnable):
    """Worker otimizado para carregar imagens com cache e múltiplos fallbacks"""
    def __init__(self, urls, cache_key=None, max_size=(300, 300), parent_cache=None):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.cache_key = cache_key
        self.max_size = max_size
        self.parent_cache = parent_cache
        self.signals = ImageLoaderSignals()
    
    @Slot()
    def run(self):
        """Tenta carregar de múltiplas URLs com cache"""
        # Verificar cache primeiro se tiver chave
        if self.cache_key and self.parent_cache and self.cache_key in self.parent_cache:
            cached_pixmap = self.parent_cache[self.cache_key]
            if cached_pixmap and not cached_pixmap.isNull():
                self.signals.finished.emit(cached_pixmap)
                return
        
        # Tentar carregar de URLs
        for url in self.urls:
            try:
                # Timeout reduzido e headers para melhor performance
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br'
                }
                response = requests.get(url, timeout=8, headers=headers, stream=True)
                
                if response.status_code == 200:
                    # Carregar apenas primeiros bytes para verificar formato
                    content = response.content
                    
                    pixmap = QPixmap()
                    if pixmap.loadFromData(content):
                        # Redimensionar se necessário para economizar memória
                        if self.max_size and (pixmap.width() > self.max_size[0] or pixmap.height() > self.max_size[1]):
                            pixmap = pixmap.scaled(
                                self.max_size[0], self.max_size[1],
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                        
                        # Salvar no cache se tiver chave
                        if self.cache_key and self.parent_cache is not None:
                            # Limpar cache se exceder limite (FIFO)
                            if '__parent_app' in self.parent_cache:
                                parent_app = self.parent_cache['__parent_app']
                                max_size = getattr(parent_app, '_max_cache_size', 100)
                                # Contar apenas chaves de imagens (excluindo __parent_app)
                                image_keys = [k for k in self.parent_cache.keys() if k != '__parent_app']
                                if len(image_keys) >= max_size:
                                    # Remover primeiro item (mais antigo), ignorando __parent_app
                                    for key in image_keys:
                                        del self.parent_cache[key]
                                        break
                            
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
