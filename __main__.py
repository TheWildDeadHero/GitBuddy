from gui import *

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitPullerConfigApp()
    window.show()
    sys.exit(app.exec())
