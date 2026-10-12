# -*- coding: utf-8 -*-
"""设计系统: 单一强调色 + 中性纸面 + 1px 边框, 无阴影/渐变/表情图标。
原则出处: Refactoring UI (Wathan & Schabot) / GNOME HIG —— 详见 README。"""

INK = "#1A1D21"        # 主文字
INK2 = "#5B6470"       # 次文字
MUTE = "#8B93A1"       # 弱文字/轴
BG = "#F7F7F5"         # 窗口底
PANEL = "#FFFFFF"      # 面板
BORDER = "#E3E5E2"     # 边框
ACCENT = "#0F766E"     # 唯一强调色(深青)
ACCENT_SOFT = "#E4F1EF"
WARN = "#B45309"
FAIL = "#B91C1C"
MONO = "Consolas"

QSS = f"""
QWidget {{ background: {BG}; color: {INK}; font-family: "Segoe UI"; font-size: 13px; }}
QToolBar {{ background: {PANEL}; border: none; border-bottom: 1px solid {BORDER}; spacing: 4px; padding: 4px 8px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 3px;
              padding: 5px 12px; color: {INK}; }}
QToolButton:hover {{ background: {ACCENT_SOFT}; }}
QToolButton:pressed {{ background: {ACCENT}; color: white; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; }}
QTabBar::tab {{ background: {PANEL}; color: {INK2}; border: 1px solid {BORDER};
               border-bottom: none; padding: 6px 22px; margin-right: 2px;
               border-top-left-radius: 3px; border-top-right-radius: 3px; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; font-weight: 600; }}
QGroupBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 3px;
            margin-top: 10px; padding: 8px 8px 8px 8px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {INK2};
                   background: {PANEL}; font-size: 12px; }}
QPushButton {{ background: {ACCENT}; color: white; border: none; border-radius: 3px;
              padding: 7px 18px; font-weight: 600; }}
QPushButton:hover {{ background: #0C5F58; }}
QPushButton:disabled {{ background: #A8C5C1; }}
QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {PANEL}; border: 1px solid {BORDER};
                           border-radius: 3px; padding: 4px 8px; selection-background-color: {ACCENT}; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QTableWidget {{ background: {PANEL}; border: 1px solid {BORDER}; gridline-color: {BORDER};
               alternate-background-color: #FAFBFA; }}
QHeaderView::section {{ background: #F0F2EF; border: none; border-bottom: 1px solid {BORDER};
                       padding: 5px 8px; font-weight: 600; color: {INK2}; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {INK2}; }}
QSplitter::handle {{ background: {BORDER}; width: 1px; }}
QScrollArea {{ border: none; }}
QLabel[class=title] {{ font-size: 21px; font-weight: 700; }}
QLabel[class=metric] {{ font-size: 17px; font-weight: 700; font-family: "{MONO}"; color: {ACCENT}; }}
QLabel[class=metricname] {{ font-size: 11px; color: {MUTE}; }}
"""
