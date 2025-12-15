"""
xcore.py - Módulo principal refatorado
Importa e re-exporta componentes do pacote core/

Este arquivo serve como ponto de compatibilidade para código legado
que ainda importa de xcore.py
"""

# Imports padrão
import os
import sys

# Imports de utils
from utils import log_message, get_steam_directory

# Utilitários
from core.utils.winrar import find_winrar, download_and_install_winrar, ensure_winrar_installed
from core.utils.hid import ensure_hid_dll

# Workers
from core.workers.download import DownloadWorkerSignals, DownloadWorker, DownloadThread
from core.workers.search import SearchWorkerSignals, SearchWorker
from core.workers.details import DetailsWorkerSignals, DetailsWorker, GameDetailsLoaderSignals, GameDetailsLoader
from core.workers.image import ImageLoaderSignals, ImageLoader
from core.workers.install import ManualInstallWorkerSignals, ManualInstallWorker

# UI - Overlays
from core.ui.overlays import (
    DownloadProgressOverlay, 
    ManualInstallProgressOverlay, 
    SpotlightOverlay
)

# UI - Screens
from core.ui.screens.download import DownloadScreen
from core.ui.screens.details import GameDetailsScreen
from core.ui.screens.manual_install import ManualInstallScreen
from core.ui.screens.installed_game import InstalledGameScreen

from core.app import GameApp

# FUNÇÃO DE INICIALIZAÇÃO

def start_software():
    """
    Inicia a aplicação principal do Games Store.
    
    Returns:
        GameApp: Instância da janela principal
    """
    ensure_hid_dll()
    window = GameApp()
    window.show()
    return window


# EXPORTAÇÕES

__all__ = [
    # Utilitários
    'find_winrar',
    'download_and_install_winrar',
    'ensure_winrar_installed',
    'ensure_hid_dll',
    
    # Workers
    'DownloadWorkerSignals',
    'DownloadWorker',
    'DownloadThread',
    'SearchWorkerSignals',
    'SearchWorker',
    'DetailsWorkerSignals',
    'DetailsWorker',
    'GameDetailsLoaderSignals',
    'GameDetailsLoader',
    'ImageLoaderSignals',
    'ImageLoader',
    'ManualInstallWorkerSignals',
    'ManualInstallWorker',
    
    # UI
    'DownloadProgressOverlay',
    'ManualInstallProgressOverlay',
    'SpotlightOverlay',
    'DownloadScreen',
    'GameDetailsScreen',
    'ManualInstallScreen',
    'InstalledGameScreen',
    
    # App
    'GameApp',
    
    # Funções
    'start_software',
]

if __name__ == "__main__":
    pass
