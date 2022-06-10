from pathlib import Path

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


class TrayIcon(QSystemTrayIcon):
    def __init__(self, app: QApplication, window: QWidget):
        self.window = window
        self.app = app
        icon_path = Path(__file__).parent / "icons/icon.png"
        icon = QIcon(str(icon_path))
        super().__init__(icon, window)
        self.setup_ui()

    def setup_ui(self):
        menu = QMenu(self.window)
        quit_action = QAction("Quit", self.window)
        quit_action.triggered.connect(lambda: self.app.quit())
        menu.addAction(quit_action)
        self.setContextMenu(menu)
