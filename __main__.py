from gitbuddy_app import *

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitBuddyApp()
    window.show()
    sys.exit(app.exec())