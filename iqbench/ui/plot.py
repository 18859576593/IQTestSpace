# -*- coding: utf-8 -*-
"""自绘折线图 (QPainter): 无 matplotlib 依赖, 视觉与主题一致。"""
import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from .theme import INK, MUTE, BORDER, ACCENT

PAD_L, PAD_R, PAD_T, PAD_B = 52, 14, 14, 34


def _nice_ticks(lo, hi, n=6):
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return [lo]
    raw = (hi - lo) / n
    mag = 10 ** np.floor(np.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    start = np.ceil(lo / step) * step
    ticks = np.arange(start, hi + step * 0.01, step)
    return ticks


class LinePlot(QWidget):
    """单曲线 + 可选标记竖线。set_series(x, y, xlabel, ylabel, xmax)。"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.x = self.y = None
        self.xlabel = self.ylabel = ""
        self.xmax = None
        self.marker_x = None       # (x, label)
        self.setMinimumHeight(190)

    def set_series(self, x, y, xlabel="", ylabel="", xmax=None, marker=None):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        self.xlabel, self.ylabel = xlabel, ylabel
        self.xmax = xmax
        self.marker_x = marker
        self.update()

    def _plot_rect(self):
        return QRectF(PAD_L, PAD_T, self.width() - PAD_L - PAD_R,
                      self.height() - PAD_T - PAD_B)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.plot = self._plot_rect()
        if self.x is None or len(self.x) < 2:
            p.setPen(QColor(MUTE))
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return
        m = (np.isfinite(self.x)) & (np.isfinite(self.y))
        x, y = self.x[m], self.y[m]
        x0, x1 = float(x.min()), self.xmax if self.xmax else float(x.max())
        y0, y1 = 0.0, max(1.05, float(y.max()) * 1.05)
        sx = (r.width() - 1) / max(x1 - x0, 1e-12)
        sy = (r.height() - 1) / max(y1 - y0, 1e-12)

        mono = QFont("Consolas", 8)
        # 网格与刻度
        p.setFont(mono)
        for tx in _nice_ticks(x0, x1):
            px = r.left() + (tx - x0) * sx
            if px > r.right():
                continue
            p.setPen(QPen(QColor(BORDER), 1))
            p.drawLine(QRectF(px, r.top(), 0, r.height()).topLeft(),
                       QRectF(px, r.top(), 0, r.height()).bottomLeft())
            p.setPen(QPen(QColor(MUTE)))
            p.drawText(QRectF(px - 30, r.bottom() + 4, 60, 16),
                       Qt.AlignHCenter, f"{tx:g}")
        for ty in _nice_ticks(y0, y1, 4):
            py = r.bottom() - (ty - y0) * sy
            p.setPen(QPen(QColor(BORDER), 1))
            p.drawLine(QRectF(r.left(), py, r.width(), 0).topLeft(),
                       QRectF(r.left(), py, r.width(), 0).topRight())
            p.setPen(QPen(QColor(MUTE)))
            p.drawText(QRectF(0, py - 8, PAD_L - 8, 16),
                       Qt.AlignRight | Qt.AlignVCenter, f"{ty:g}")
        # 轴标签
        p.drawText(QRectF(r.left(), self.height() - 14, r.width(), 12),
                   Qt.AlignHCenter, self.xlabel)
        p.save()
        p.translate(12, r.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-60, -6, 120, 12), Qt.AlignHCenter, self.ylabel)
        p.restore()
        # 曲线
        pen = QPen(QColor(ACCENT), 2)
        pen.setCosmetic(True)
        p.setPen(pen)
        pts = [QRectF(r.left() + (xx - x0) * sx, r.bottom() - (yy - y0) * sy, 0, 0)
               .topLeft() for xx, yy in zip(x, y)]
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])
        # 标记线 (如 MTF50)
        if self.marker_x and self.marker_x[0] is not None and np.isfinite(self.marker_x[0]):
            mx = r.left() + (self.marker_x[0] - x0) * sx
            if r.left() <= mx <= r.right():
                dash = QPen(QColor(INK), 1, Qt.DashLine)
                p.setPen(dash)
                p.drawLine(QRectF(mx, r.top(), 0, r.height()).topLeft(),
                           QRectF(mx, r.top(), 0, r.height()).bottomLeft())
                p.setPen(QPen(QColor(INK)))
                p.drawText(QRectF(mx + 4, r.top() + 4, 120, 14),
                           Qt.AlignLeft, self.marker_x[1])
        # 标题
        p.setPen(QPen(QColor(INK)))
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(r.left(), 2, r.width(), 14), Qt.AlignLeft, self.title)
