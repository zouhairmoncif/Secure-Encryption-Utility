import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from gui.seu import SeuController


def main():
    # Crisp, scaled rendering on high-DPI displays.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Secure Encryption Utility")
    app.setOrganizationName("Secure Encryption Utility")

    window = SeuController()
    window.resize(960, 600)
    window.show()
    window.setFocus()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()