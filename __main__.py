# __main__.py

import sys
from PySide6.QtWidgets import QApplication
from gitbuddy_app import GitBuddyApp

if __name__ == "__main__":
    # Ensure QApplication is created before QSystemTrayIcon
    app = QApplication(sys.argv)
    window = GitBuddyApp()
    window.show() # Show the main window initially
    sys.exit(app.exec())
