import os
import sys
import datax
import xcore
import updater
from uxmod import softwarerei
from PyQt5.QtGui import QColor
from version import __version__
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
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
    
    window = softwarerei()
    window.show()
    
    QTimer.singleShot(3000, lambda: check_updates(window))
    
    sys.exit(app.exec_())


def check_updates(window):
    try:
        updater.check_and_update(window, show_no_update_message=False)
    except Exception as e:
        print(f"Erro ao verificar atualizações: {e}")


if __name__ == "__main__":
    main()
