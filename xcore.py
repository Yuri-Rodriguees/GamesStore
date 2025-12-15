
import os
import sys
from utils import log_message, get_steam_directory
from core.utils.winrar import find_winrar, download_and_install_winrar, ensure_winrar_installed
from core.utils.hid import ensure_hid_dll
from core.workers.download import DownloadWorkerSignals, DownloadWorker, DownloadThread
from core.workers.search import SearchWorkerSignals, SearchWorker
from core.workers.details import DetailsWorkerSignals, DetailsWorker, GameDetailsLoaderSignals, GameDetailsLoader
from core.workers.image import ImageLoaderSignals, ImageLoader
from core.workers.install import ManualInstallWorkerSignals, ManualInstallWorker
from core.ui.overlays import (
    DownloadProgressOverlay, 
    ManualInstallProgressOverlay, 
    SpotlightOverlay
)
from core.ui.screens.download import DownloadScreen
from core.ui.screens.details import GameDetailsScreen
from core.ui.screens.manual_install import ManualInstallScreen
from core.ui.screens.installed_game import InstalledGameScreen
from core.app import GameApp

def start_software():

    ensure_hid_dll()
    window = GameApp()
    window.show()
    return window


__all__ = [

    # Utilitários
    'find_winrar',
    'download_and_install_winrar',
    'ensure_winrar_installed',
    'ensure_hid_dll',
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
    'DownloadProgressOverlay',
    'ManualInstallProgressOverlay',
    'SpotlightOverlay',
    'DownloadScreen',
    'GameDetailsScreen',
    'ManualInstallScreen',
    'InstalledGameScreen',
    'GameApp',
    'start_software',
]

if __name__ == "__main__":
    pass
