# -*- coding: utf-8 -*-
"""主窗口: ColorChecker / SFR 双模块工作台。左=图像+框选ROI, 右=参数+结果。"""
import csv
import datetime
import os

import cv2
import numpy as np
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QColor, QAction, QImage
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsView, QGraphicsScene, QRubberBand, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QScrollArea, QToolBar, QMessageBox, QFileDialog, QGraphicsRectItem, QHeaderView,
)

from .theme import QSS, ACCENT, WARN, MONO
from .plot import LinePlot
from .. import refs, colorcheck, sfr, chartdetect, __version__


def imread_unicode(path):
    """中文路径安全读图 → RGB ndarray。"""
    data = np.fromfile(path, dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def ndarray_to_qpixmap(arr):
    h, w, _ = arr.shape
    return QPixmap.fromImage(QImage(arr.data, w, h, 3 * w, QImage.Format_RGB888))


class ImageViewer(QGraphicsView):
    """图像显示 + 橡皮筋框选 ROI + 覆盖层(色块网格/ROI框)。"""

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())
        from PySide6.QtGui import QPainter
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._origin = None
        self._band = QRubberBand(QRubberBand.Rectangle, self)
        self._img = None
        self._overlays = []

    def set_image(self, arr):
        self._img = arr
        sc = self.scene()
        sc.clear()
        self._overlays = []
        sc.addPixmap(ndarray_to_qpixmap(arr))
        sc.setSceneRect(0, 0, arr.shape[1], arr.shape[0])
        self.fitInView(sc.sceneRect(), Qt.KeepAspectRatio)

    @property
    def has_image(self):
        return self._img is not None

    def mousePressEvent(self, e):
        if self._img is not None and e.button() == Qt.LeftButton:
            self._origin = self.mapToScene(e.position().toPoint())
            self._band.setGeometry(QRect(e.position().toPoint(), e.position().toPoint()))
            self._band.show()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            p0 = self.mapFromScene(self._origin)
            self._band.setGeometry(QRect(p0, e.position().toPoint()).normalized())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._origin is not None:
            self._band.hide()
            p1 = self.mapToScene(e.position().toPoint())
            x0, y0 = int(min(self._origin.x(), p1.x())), int(min(self._origin.y(), p1.y()))
            w, h = int(abs(p1.x() - self._origin.x())), int(abs(p1.y() - self._origin.y()))
            self._origin = None
            if w > 4 and h > 4:
                self._roi = (x0, y0, w, h)
                self._draw_overlays()
        super().mouseReleaseEvent(e)

    def set_roi_draw(self, roi):
        self._roi = roi
        self._draw_overlays()

    def _draw_overlays(self):
        for it in self._overlays:
            self.scene().removeItem(it)
        self._overlays = []
        roi = getattr(self, "_roi", None)
        if roi:
            it = self.scene().addRect(roi[0], roi[1], roi[2], roi[3],
                                      QColor(ACCENT), QColor(0, 0, 0, 0))
            self._overlays.append(it)
        for (x, y, w, h), ok in getattr(self, "_boxes", []):
            color = QColor("#2E9E44") if ok else QColor(WARN)
            self._overlays.append(
                self.scene().addRect(x, y, w, h, color, QColor(0, 0, 0, 0)))

    def set_boxes(self, boxes):
        """boxes: [((x,y,w,h), ok), ...] 自动识别色块框"""
        self._boxes = boxes
        self._draw_overlays()

    def get_roi(self):
        return getattr(self, "_roi", None)

    def resizeEvent(self, ev):
        if self._img is not None:
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        super().resizeEvent(ev)


class MetricLabel(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        lay = QHBoxLayout(self)
        self.value = QLabel("—")
        self.value.setProperty("class", "metric")
        lay.addWidget(self.value)

    def set(self, text, warn=False):
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {WARN if warn else ACCENT};")


class SwatchStrip(QWidget):
    """参考色 vs 实测色 成对色块条。"""

    def __init__(self):
        super().__init__()
        self.pairs = []   # (ref_rgb, meas_rgb)
        self.setMinimumHeight(64)

    def set_pairs(self, ref_lab, meas_rgb):
        from ..colorcheck import lab_to_srgb
        self.ref_rgb = lab_to_srgb(np.asarray(ref_lab))
        self.meas = np.asarray(meas_rgb)
        self.update()

    def paintEvent(self, ev):
        from PySide6.QtGui import QPainter
        if not hasattr(self, "ref_rgb"):
            return
        p = QPainter(self)
        n = len(self.ref_rgb)
        w = self.width() / n
        h2 = self.height() / 2
        for i in range(n):
            r, g, b = self.ref_rgb[i]
            p.fillRect(int(i * w), 0, int(w) + 1, int(h2), QColor(r, g, b))
            r, g, b = self.meas[i]
            p.fillRect(int(i * w), int(h2), int(w) + 1, int(h2), QColor(r, g, b))
        p.end()


class ColorTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.result = None
        self.img = None
        self.path = None
        sp = QSplitter(Qt.Horizontal)
        left = QGroupBox("图像 — 框选色卡区域(整卡)")
        lv = QVBoxLayout(left)
        self.viewer = ImageViewer()
        lv.addWidget(self.viewer)
        sp.addWidget(left)
        right = QScrollArea()
        right.setWidgetResizable(True)
        panel = QWidget()
        rv = QVBoxLayout(panel)
        g1 = QGroupBox("参数")
        f = QFormLayout(g1)
        self.sp_rows = QSpinBox(); self.sp_rows.setRange(1, 12); self.sp_rows.setValue(4)
        self.sp_cols = QSpinBox(); self.sp_cols.setRange(1, 12); self.sp_cols.setValue(6)
        self.sp_inner = QDoubleSpinBox(); self.sp_inner.setRange(0.1, 0.9); self.sp_inner.setValue(0.4)
        self.sp_inner.setSingleStep(0.05)
        f.addRow("行数", self.sp_rows); f.addRow("列数", self.sp_cols)
        f.addRow("采样内比例", self.sp_inner)
        self.btn = QPushButton("分 析")
        self.btn.clicked.connect(self.analyze)
        f.addRow(self.btn)
        self.btn_auto = QPushButton("自动识别色块")
        self.btn_auto.setStyleSheet(
            "background: #FFFFFF; color: #0F766E; border: 1px solid #0F766E;")
        self.btn_auto.clicked.connect(self.auto_detect)
        f.addRow(self.btn_auto)
        rv.addWidget(g1)
        self.m_e00 = MetricLabel("平均 ΔE2000"); self.m_e76 = MetricLabel("平均 ΔE76")
        self.m_c = MetricLabel("平均 ΔC76"); self.m_wb = MetricLabel("WB误差(灰块ΔE00)")
        for m in (self.m_e00, self.m_e76, self.m_c, self.m_wb):
            rv.addWidget(m)
        g2 = QGroupBox("参考色(上) vs 实测色(下)")
        v2 = QVBoxLayout(g2); self.swatch = SwatchStrip(); v2.addWidget(self.swatch)
        rv.addWidget(g2)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["#", "色块", "参考 L*a*b*", "实测 L*a*b*", "ΔE00", "ΔE76", "ΔC76"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        rv.addWidget(self.table, 1)
        right.setWidget(panel)
        sp.addWidget(right)
        sp.setSizes([720, 430])
        lay = QHBoxLayout(self)
        lay.addWidget(sp)

    def load(self, arr, path):
        self.img = arr
        self.path = path
        self.patch_rects = None
        self.viewer._boxes = []
        self.viewer.set_image(arr)

    def auto_detect(self):
        if self.img is None:
            self.log("请先打开图像"); return
        rects, oks, n = chartdetect.detect_patches(
            self.img, self.sp_rows.value(), self.sp_cols.value())
        if rects is None:
            self.viewer._boxes = []
            self.viewer._draw_overlays()
            self.log("自动识别失败 — 请改用框选整卡区域(确保色卡完整、光线均匀)")
            return
        self.patch_rects = rects
        self.viewer.set_boxes(list(zip(rects, oks)))
        miss = len(rects) - n
        if miss:
            self.log(f"识别到 {n}/{len(rects)} 块(橙色为推补), 可直接分析或手动框选修正")
        else:
            self.log(f"识别 {n}/{len(rects)} 块完成 — 直接点「分析」")
        self.analyze()

    def analyze(self):
        if self.img is None:
            self.log("请先打开图像"); return
        try:
            if getattr(self, "patch_rects", None):
                self.result = colorcheck.analyze_rects(
                    self.img, self.patch_rects, refs.CC24_POST2014_D50,
                    self.sp_inner.value())
            else:
                roi = self.viewer.get_roi()
                if not roi:
                    self.log("请先「自动识别色块」, 或在图上框选色卡区域(拖拽)")
                    return
                self.result = colorcheck.analyze(
                    self.img, roi, refs.CC24_POST2014_D50,
                    self.sp_rows.value(), self.sp_cols.value(),
                    self.sp_inner.value())
        except Exception as e:
            self.log(f"分析失败: {e}"); return
        r = self.result
        self.m_e00.set(f"{r.mean_e00:.2f}", r.mean_e00 > 5)
        self.m_e76.set(f"{r.mean_e76:.2f}")
        self.m_c.set(f"{r.mean_c76:.2f}")
        self.m_wb.set(f"{r.wb_error:.2f}", r.wb_error > 3)
        self.swatch.set_pairs(r.ref_lab, r.meas_rgb)
        self.table.setRowCount(len(r.de00))
        for i in range(len(r.de00)):
            vals = [str(i + 1), refs.PATCH_NAMES[i] if i < len(refs.PATCH_NAMES) else "",
                    "/".join(f"{v:.0f}" for v in r.ref_lab[i]),
                    "/".join(f"{v:.0f}" for v in r.meas_lab[i]),
                    f"{r.de00[i]:.2f}", f"{r.de76[i]:.2f}", f"{r.dc76[i]:.2f}"]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c >= 4:
                    item.setFont(MONO_FONT())
                self.table.setItem(i, c, item)
        self.log(f"ColorChecker 完成: meanΔE00={r.mean_e00:.2f} max={r.max_e00:.2f}")

    def save_report(self, folder):
        r = self.result
        if not r:
            return None
        fp = os.path.join(folder, f"colorcheck_{_ts()}.csv")
        with open(fp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["#", "名称", "refL", "refa", "refb", "measL", "measa", "measb",
                        "dE00", "dE76", "dC76"])
            for i in range(len(r.de00)):
                w.writerow([i + 1, refs.PATCH_NAMES[i] if i < len(refs.PATCH_NAMES) else "",
                            *r.ref_lab[i].round(2), *r.meas_lab[i].round(2),
                            round(float(r.de00[i]), 3), round(float(r.de76[i]), 3),
                            round(float(r.dc76[i]), 3)])
            w.writerow([])
            w.writerow(["mean_dE00", round(r.mean_e00, 3), "mean_dE76", round(r.mean_e76, 3),
                        "mean_dC76", round(r.mean_c76, 3), "WB_gray_dE00", round(r.wb_error, 3)])
        return fp


class SFRTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.img = None
        self.result = None
        sp = QSplitter(Qt.Horizontal)
        left = QGroupBox("图像 — 框选一条斜边区域(近垂直, 约5°)")
        lv = QVBoxLayout(left)
        self.viewer = ImageViewer()
        lv.addWidget(self.viewer)
        sp.addWidget(left)
        right = QScrollArea(); right.setWidgetResizable(True)
        panel = QWidget(); rv = QVBoxLayout(panel)
        g1 = QGroupBox("参数")
        f = QFormLayout(g1)
        self.ed_pitch = QDoubleSpinBox(); self.ed_pitch.setRange(0, 20)
        self.ed_pitch.setDecimals(3); self.ed_pitch.setValue(0.0)
        self.ed_pitch.setSpecialValueText("不换算")
        f.addRow("像素间距 (μm)", self.ed_pitch)
        self.btn = QPushButton("分 析")
        self.btn.clicked.connect(self.analyze)
        f.addRow(self.btn)
        rv.addWidget(g1)
        self.m_50 = MetricLabel("MTF50 (cy/px)")
        self.m_50mm = MetricLabel("MTF50 (lp/mm)")
        self.m_30 = MetricLabel("MTF30 (cy/px)")
        self.m_ang = MetricLabel("边角度 (°)")
        for m in (self.m_50, self.m_50mm, self.m_30, self.m_ang):
            rv.addWidget(m)
        self.p_esf = LinePlot("ESF 边扩散函数")
        self.p_mtf = LinePlot("MTF 调制传递函数")
        rv.addWidget(self.p_esf)
        rv.addWidget(self.p_mtf)
        right.setWidget(panel)
        sp.addWidget(right)
        sp.setSizes([720, 430])
        lay = QHBoxLayout(self); lay.addWidget(sp)

    def load(self, arr, path):
        self.img = arr
        self.viewer.set_image(arr)

    def analyze(self):
        if self.img is None:
            self.log("请先打开图像"); return
        roi = self.viewer.get_roi()
        if not roi:
            self.log("请先框选包含斜边的小区域(建议 50~200px 见方)"); return
        x, y, w, h = roi
        gray = self.img[y:y + h, x:x + w].mean(axis=2)
        try:
            self.result = sfr.analyze(gray)
        except Exception as e:
            self.log(f"分析失败: {e}"); return
        r = self.result
        self.m_50.set(f"{r.mtf50:.4f}")
        if self.ed_pitch.value() > 0:
            self.m_50mm.set(f"{sfr.mtf50_lpmm(r.mtf50, self.ed_pitch.value()):.1f}")
        else:
            self.m_50mm.set("需填间距")
        self.m_30.set(f"{r.mtf30:.4f}")
        self.m_ang.set(f"{r.angle_deg:.2f}")
        self.p_esf.set_series(r.esf_u, r.esf, "位置 (px)", "亮度")
        m = r.freq <= 1.5
        self.p_mtf.set_series(r.freq[m], r.mtf[m], "频率 (cy/pixel)", "MTF",
                              marker=(r.mtf50, f"MTF50={r.mtf50:.3f}"))
        self.log(f"SFR 完成: MTF50={r.mtf50:.4f} cy/px, 角度{r.angle_deg:.1f}°")

    def save_report(self, folder):
        r = self.result
        if not r:
            return None
        fp = os.path.join(folder, f"sfr_{_ts()}.csv")
        with open(fp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["freq_cy_px", "mtf"])
            for a, b in zip(r.freq, r.mtf):
                w.writerow([round(float(a), 5), round(float(b), 5)])
            w.writerow([])
            w.writerow(["MTF50_cy_px", round(r.mtf50, 5),
                        "MTF30", round(r.mtf30, 5), "MTF10", round(r.mtf10, 5),
                        "angle_deg", round(r.angle_deg, 3),
                        "Nyquist_MTF", round(r.nyquist_mtf, 4)])
        return fp


def MONO_FONT():
    from PySide6.QtGui import QFont
    f = QFont(MONO)
    return f


def _ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"IQBench 客观指标工作台 v{__version__}")
        self.resize(1420, 860)
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)
        a_open = QAction("打开图像", self)
        a_open.triggered.connect(self.open_image)
        a_save = QAction("保存报告 (CSV)", self)
        a_save.triggered.connect(self.save_reports)
        a_test = QAction("引擎自检", self)
        a_test.triggered.connect(self.selftest)
        a_about = QAction("关于", self)
        a_about.triggered.connect(self.about)
        for a in (a_open, a_save, a_test, a_about):
            tb.addAction(a)
        self.tabs = QTabWidget()
        self.logbar = self.statusBar()
        self._log = lambda m: self.logbar.showMessage(m, 8000)
        self.tab_cc = ColorTab(self._log)
        self.tab_sfr = SFRTab(self._log)
        self.tabs.addTab(self.tab_cc, "ColorChecker 色卡")
        self.tabs.addTab(self.tab_sfr, "SFR 斜边锐度")
        self.setCentralWidget(self.tabs)
        self.logbar.showMessage("就绪 — 打开图像后, 在图上拖拽框选 ROI")

    def open_image(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "打开图像", "", "图像 (*.jpg *.jpeg *.png *.bmp *.tif *.tiff)")
        if not fp:
            return
        arr = imread_unicode(fp)
        if arr is None:
            QMessageBox.warning(self, "错误", "无法解码图像"); return
        self.tab_cc.load(arr, fp)
        self.tab_sfr.load(arr, fp)
        self.log(f"已载入 {os.path.basename(fp)} ({arr.shape[1]}×{arr.shape[0]})")

    def save_reports(self):
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "reports")
        os.makedirs(folder, exist_ok=True)
        fps = [t.save_report(folder) for t in (self.tab_cc, self.tab_sfr)]
        fps = [f for f in fps if f]
        if fps:
            self.log("已保存: " + "; ".join(os.path.basename(f) for f in fps))
        else:
            self.log("没有可保存的结果")

    def selftest(self):
        from .. import selftest as st
        code = st.run()
        QMessageBox.information(self, "引擎自检",
                                "全部通过 — 引擎锚点验证合格" if code == 0 else "存在失败项, 见控制台输出")

    def about(self):
        QMessageBox.about(
            self, "IQBench",
            f"IQBench v{__version__}\n图像客观指标测试工作台\n\n"
            "模块: ColorChecker (ΔE76/ΔE2000/ΔC76) · SFR (斜边 MTF)\n"
            "色彩链路: sRGB→XYZ(D65)→Bradford→Lab(D50)\n"
            "SFR: ISO 12233 斜边法, 8× 过采样\n\n参考值: X-Rite ColorChecker Classic post-2014")
