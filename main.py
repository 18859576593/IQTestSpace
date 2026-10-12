# -*- coding: utf-8 -*-
"""IQBench 入口。--selftest 走无界面引擎自检。"""
import sys


def main():
    if "--selftest" in sys.argv:
        from iqbench import selftest
        return selftest.run()
    from PySide6.QtWidgets import QApplication
    from iqbench.ui.theme import QSS
    from iqbench.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
