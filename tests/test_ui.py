import sys
import unittest
from PyQt5.QtWidgets import QApplication

from PyQt5.QtWidgets import QApplication, QWidget

# Mock
class MockApp(QWidget):
    def __init__(self):
        super().__init__()
        self.image_cache = {}
        self.thread_pool = Conf()
        self.pages = Conf()
    def start_download_from_api(self, *args):
        pass

class Conf:
    def start(self, *args): pass
    def setCurrentIndex(self, *args): pass

# Import target
from core.ui.screens.details import GameDetailsScreen

class TestGameDetailsScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Cria app global necessário para widgets
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_init(self):
        """Testa se a tela inicializa corretamente com dados mockados"""
        details = {
            'nome': 'Jogo Teste',
            'disponivel_download': True,
            'data_lancamento': '2023-01-01',
            'desenvolvedores': ['Dev1'],
            'generos': ['Action'],
            'descricao': 'Descricao teste'
        }
        screen = GameDetailsScreen(MockApp(), 123, details)
        
        # Validações básicas
        self.assertIsNotNone(screen)
        
        # Encontrar botão e testar texto
        buttons = screen.findChildren(QPushButton)
        download_btn = [b for b in buttons if "BAIXAR" in b.text()][0]
        self.assertTrue(download_btn.isEnabled())

if __name__ == '__main__':
    unittest.main()
