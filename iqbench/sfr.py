# -*- coding: utf-8 -*-
"""SFR 指标引擎: 斜边法 (ISO 12233 流程, sfrmat 风格)。
流程: 梯度质心定位边(质量集中在边上, 不受台阶不对称影响) → 最小二乘拟合边角度
→ 投影坐标 8× 过采样分箱(±16px 窗) → ESF → 3点平滑 → 差分得 LSF → 去基线
→ |FFT| 归一化 → MTF → MTF50/30/10。纯 numpy。
"""
import numpy as np


class SFRResult:
    def __init__(self, esf_u, esf, freq, mtf, angle_deg, oversample):
        self.esf_u = esf_u
        self.esf = esf
        self.freq = freq        # cy/pixel
        self.mtf = mtf
        self.angle_deg = angle_deg
        self.oversample = oversample

    @staticmethod
    def _cross(freq, mtf, level):
        """MTF 首次下穿 level 的频率(线性插值)。"""
        below = np.where(mtf < level)[0]
        if len(below) == 0 or below[0] == 0:
            return float("nan")
        i = below[0]
        y0, y1 = mtf[i - 1], mtf[i]
        if y1 == y0:
            return float(freq[i])
        return float(freq[i - 1] + (level - y0) * (freq[i] - freq[i - 1]) / (y1 - y0))

    @property
    def mtf50(self):
        return self._cross(self.freq, self.mtf, 0.5)

    @property
    def mtf30(self):
        return self._cross(self.freq, self.mtf, 0.3)

    @property
    def mtf10(self):
        return self._cross(self.freq, self.mtf, 0.1)

    @property
    def nyquist_mtf(self):
        i = np.searchsorted(self.freq, 0.5)
        return float(self.mtf[i]) if i < len(self.mtf) else float("nan")


def analyze(roi_gray, oversample=8, half_window=16):
    """roi_gray: 2D uint8/float, 包含一条近似垂直的斜边(约±20°内)。"""
    g = np.asarray(roi_gray, dtype=np.float64)
    H, W = g.shape
    y = np.arange(H, dtype=np.float64)
    x = np.arange(W, dtype=np.float64)
    # 梯度质心: 行内 |dI/dx| 的重心 = 边位置(对称于边, 无台阶偏置)
    gx = np.gradient(g, axis=1)
    wgt = np.abs(gx) + 1e-9
    tot = wgt.sum(axis=1)
    bad = tot < 1e-6
    wgt[bad] = 1.0
    xc = (wgt * x[None, :]).sum(axis=1) / wgt.sum(axis=1)
    a, b = np.polyfit(y[~bad], xc[~bad], 1)
    angle = float(np.degrees(np.arctan(a)))
    if abs(angle) > 25:
        raise ValueError("边角度 %.1f° 过大(>25°), 请用近似垂直的边或旋转图像" % angle)
    # 投影坐标(单位 1/oversample px), 只取边 ±half_window 的窗口
    u = (x[None, :] - (a * y[:, None] + b)) * oversample
    m = np.abs(u) <= half_window * oversample
    ub = np.floor(u[m]).astype(np.int64) + half_window * oversample
    nb = 2 * half_window * oversample
    cnt = np.bincount(ub, minlength=nb).astype(np.float64)
    s = np.bincount(ub, weights=g[m], minlength=nb)
    keep = cnt >= 3
    if keep.sum() < 2 * oversample:
        raise ValueError("有效采样点过少, ROI 太小或边不清晰")
    esf = s[keep] / np.maximum(cnt[keep], 1)
    # 3点滑动平均(端点保持原值——convolve 'same' 的零填充会在两端造假边)
    if len(esf) > 4:
        esf = np.concatenate([esf[:1],
                              np.convolve(esf, np.ones(3) / 3.0, mode="valid"),
                              esf[-1:]])
    lsf = np.gradient(esf) * oversample
    n = len(lsf)
    tail = max(1, n // 10)
    lsf = lsf - np.concatenate([lsf[:tail], lsf[-tail:]]).mean()
    mtf = np.abs(np.fft.rfft(lsf))
    if mtf[0] == 0:
        raise ValueError("LSF 能量为零")
    mtf = mtf / mtf[0]
    freq = np.arange(len(mtf)) / (n / oversample)  # cy/pixel
    us = (np.arange(nb)[keep] - half_window * oversample) / oversample
    return SFRResult(us, esf, freq, mtf, angle, oversample)


def mtf50_lpmm(freq_cy_px, pitch_um):
    """cy/pixel → lp/mm (pitch_um: 像素间距, 单位μm)。"""
    return freq_cy_px / (pitch_um * 1e-3)
