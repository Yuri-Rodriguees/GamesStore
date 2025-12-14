# Core module init
# Expõe classes principais para facilitar importações

from core.app import GameApp
from core.utils.winrar import find_winrar, download_and_install_winrar, ensure_winrar_installed
from core.utils.hid import ensure_hid_dll

# Workers
from core.workers.download import DownloadWorkerSignals, DownloadWorker, DownloadThread
from core.workers.search import SearchWorkerSignals, SearchWorker
from core.workers.details import DetailsWorkerSignals, DetailsWorker, GameDetailsLoaderSignals, GameDetailsLoader
from core.workers.image import ImageLoaderSignals, ImageLoader
from core.workers.install import ManualInstallWorkerSignals, ManualInstallWorker

# UI
from core.ui.overlays import DownloadProgressOverlay, ManualInstallProgressOverlay, SpotlightOverlay
from core.ui.screens.download import DownloadScreen
from core.ui.screens.details import GameDetailsScreen
from core.ui.screens.manual_install import ManualInstallScreen
from core.ui.screens.installed_game import InstalledGameScreen

__all__ = [
    # Main App
    'GameApp',
    
    # Utils
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
]
