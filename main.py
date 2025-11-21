import os
import sys
import updater
import uxmod
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

# Importação mais robusta para módulos compilados
try:
    from uxmod import softwarerei
except ImportError:
    # Fallback: importar o módulo e acessar a classe
    softwarerei = getattr(uxmod, 'softwarerei', None)
    if softwarerei is None:
        raise ImportError("Não foi possível importar 'softwarerei' de 'uxmod'")


def setup_dark_palette(app):
    """Configura a paleta de cores escura para a aplicação"""
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, QColor(31, 31, 31))
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    dark_palette.setColor(dark_palette.Base, QColor(35, 35, 35))
    dark_palette.setColor(dark_palette.AlternateBase, QColor(31, 31, 31))
    dark_palette.setColor(dark_palette.ToolTipBase, Qt.white)
    dark_palette.setColor(dark_palette.ToolTipText, Qt.white)
    dark_palette.setColor(dark_palette.Text, Qt.white)
    dark_palette.setColor(dark_palette.Button, QColor(45, 45, 45))
    dark_palette.setColor(dark_palette.ButtonText, Qt.white)
    dark_palette.setColor(dark_palette.BrightText, Qt.red)
    dark_palette.setColor(dark_palette.Link, QColor(100, 180, 255))
    dark_palette.setColor(dark_palette.Highlight, QColor(100, 180, 255))
    dark_palette.setColor(dark_palette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    setup_dark_palette(app)
    
    window = softwarerei()
    window.show()
    
    QTimer.singleShot(3000, lambda: check_updates(window))
    
    sys.exit(app.exec_())


def check_updates(window):
    try:
        # Verificar versão atual para decidir se deve verificar beta
        try:
            from version import __version__
            check_beta = "-old" in __version__.lower()
        except:
            check_beta = False
        
        updater.check_and_update(window, show_no_update_message=False, check_beta=check_beta)
    except Exception as e:
        print(f"Erro ao verificar atualizações: {e}")


if __name__ == "__main__":
    main()
