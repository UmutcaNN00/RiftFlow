import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication
from src.ui.main_window_v2 import MainWindowV2

def main():
    try:
        myappid = 'riftflow.lol.assistant.v2'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindowV2()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
