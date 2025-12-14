"""
Workers de detalhes do jogo - DetailsWorker, GameDetailsLoader
"""
import requests

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot as Slot


class DetailsWorkerSignals(QObject):
    """Sinais para carregar detalhes do jogo"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)


class DetailsWorker(QRunnable):
    """Worker para buscar detalhes do jogo"""
    
    def __init__(self, app_id, api_url_site):
        super().__init__()
        self.app_id = app_id
        self.api_url_site = api_url_site
        self.signals = DetailsWorkerSignals()
    
    @Slot()
    def run(self):
        try:
            url = f"{self.api_url_site}/detalhes-jogo/{self.app_id}"
            
            response = requests.get(url, timeout=15)
            data = response.json()
            
            if data.get('status') == 'success':
                self.signals.finished.emit(data)
            else:
                self.signals.error.emit(data.get('message', 'Erro desconhecido'))
        except Exception as e:
            self.signals.error.emit(str(e))


class GameDetailsLoaderSignals(QObject):
    """Sinais para carregar detalhes do jogo"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)


class GameDetailsLoader(QRunnable):
    """Worker para buscar detalhes do jogo na Steam API"""
    def __init__(self, app_id, api_url_site):
        super().__init__()
        self.app_id = app_id
        self.api_url_site = api_url_site
        self.signals = GameDetailsLoaderSignals()
    
    @Slot()
    def run(self):
        try:
            # Buscar dados da Steam API
            steam_url = f"https://store.steampowered.com/api/appdetails?appids={self.app_id}&l=portuguese"
            response = requests.get(steam_url, timeout=10)
            data = response.json()
            
            if str(self.app_id) in data and data[str(self.app_id)].get('success'):
                game_data = data[str(self.app_id)]['data']
                
                # Verificar disponibilidade na sua API
                availability = self.check_availability()
                
                details = {
                    'name': game_data.get('name', 'Jogo'),
                    'short_description': game_data.get('short_description', 'Sem descrição'),
                    'header_image': game_data.get('header_image', ''),
                    'screenshots': [s.get('path_full') for s in game_data.get('screenshots', [])[:3]],
                    'genres': [g.get('description') for g in game_data.get('genres', [])],
                    'developers': game_data.get('developers', []),
                    'publishers': game_data.get('publishers', []),
                    'release_date': game_data.get('release_date', {}).get('date', 'N/A'),
                    'price': game_data.get('price_overview', {}).get('final_formatted', 'Grátis'),
                    'available_download': availability['available'],
                    'keys_count': availability['keys_count']
                }
                
                self.signals.finished.emit(details)
            else:
                self.signals.error.emit("Jogo não encontrado na Steam")
                
        except Exception as e:
            self.signals.error.emit(f"Erro ao carregar: {str(e)}")
    
    def check_availability(self):
        """Verifica se o jogo está disponível na sua API"""
        try:
            url = f"{self.api_url_site}/verificar-jogo/{self.app_id}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'available': True,
                    'keys_count': data.get('keys_disponiveis', 0)
                }
        except:
            pass
        
        return {'available': False, 'keys_count': 0}
