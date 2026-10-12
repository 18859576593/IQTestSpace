# -*- coding: utf-8 -*-
"""ColorChecker 指标引擎: 色块采样 → Lab(D50) → ΔE76 / ΔC76 / ΔE2000。
色彩链路: sRGB(8bit) → 线性化(sRGB EOTF) → XYZ(D65) → Bradford 自适应 → XYZ(D50)
→ CIELAB(D50白) → 与参考值(同D50)求差。纯 numpy, 无其它依赖。
"""
import numpy as np

# sRGB→XYZ(D65) 线性矩阵
_M_RGB2XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041]])
# Bradford D65→D50 色适应
_M_BRADFORD = np.array([
    [1.0478112, 0.0228866, -0.0501270],
    [0.0295424, 0.9904844, -0.0170491],
    [-0.0092345, 0.0150436, 0.7521316]])
_WP_D50 = np.array([0.9642, 1.0, 0.8251])
_EPS = 216.0 / 24389.0
_KAPPA = 24389.0 / 27.0


def srgb_to_linear(rgb_u8):
    """sRGB 8bit → 线性 RGB(D65), (N,3)。"""
    c = np.asarray(rgb_u8, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_to_lab(rgb_u8):
    """rgb_u8: (N,3) uint8/float 0~255 → (N,3) Lab(D50)。"""
    lin = srgb_to_linear(rgb_u8)
    xyz = lin @ _M_RGB2XYZ.T
    xyz = xyz @ _M_BRADFORD.T
    t = xyz / _WP_D50
    f = np.where(t > _EPS, np.cbrt(t), (_KAPPA * t + 16.0) / 116.0)
    L = 116.0 * f[:, 1] - 16.0
    a = 500.0 * (f[:, 0] - f[:, 1])
    b = 200.0 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def lab_to_linear_rgb(lab):
    """Lab(D50) → 线性 RGB(D65), (N,3)。"""
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    def finv(f):
        f3 = f ** 3
        return np.where(f3 > _EPS, f3, (116.0 * f - 16.0) / _KAPPA)
    xyz = np.stack([finv(fx), finv(fy), finv(fz)], axis=1) * _WP_D50
    return xyz @ np.linalg.inv(_M_BRADFORD.T) @ np.linalg.inv(_M_RGB2XYZ.T)


def linear_to_srgb_u8(lin):
    """线性 RGB(D65) → sRGB 8bit (clip 到 [0,1])。"""
    srgb = np.where(lin <= 0.0031308, 12.92 * lin,
                    1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055)
    return np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def lab_to_srgb(lab):
    """Lab(D50) → sRGB 8bit (合成自检用)。"""
    return linear_to_srgb_u8(lab_to_linear_rgb(lab))


def delta_e76(ref, meas):
    return np.linalg.norm(np.asarray(ref) - np.asarray(meas), axis=-1)


def delta_c76(ref, meas):
    d = np.asarray(ref) - np.asarray(meas)
    return np.hypot(d[..., 1], d[..., 2])


def delta_e2000(ref, meas):
    """CIEDE2000 (kL=kC=kH=1)。ref/meas: (N,3) Lab。"""
    L1, a1, b1 = np.asarray(ref).T
    L2, a2, b2 = np.asarray(meas).T
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cb = 0.5 * (C1 + C2)
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    ap1 = (1 + G) * a1
    ap2 = (1 + G) * a2
    Cp1 = np.hypot(ap1, b1)
    Cp2 = np.hypot(ap2, b2)
    hp1 = np.degrees(np.arctan2(b1, ap1)) % 360
    hp2 = np.degrees(np.arctan2(b2, ap2)) % 360
    dL = L2 - L1
    dC = Cp2 - Cp1
    dhp = hp2 - hp1
    dhp = np.where(dhp > 180, dhp - 360, dhp)
    dhp = np.where(dhp < -180, dhp + 360, dhp)
    dH = 2 * np.sqrt(Cp1 * Cp2) * np.sin(np.radians(dhp) / 2)
    Lbp = 0.5 * (L1 + L2)
    Cbp = 0.5 * (Cp1 + Cp2)
    hbp = np.where(np.abs(hp1 - hp2) > 180, 0.5 * (hp1 + hp2 + 360), 0.5 * (hp1 + hp2))
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30))
         + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6))
         - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dL / Sl) ** 2 + (dC / Sc) ** 2
                   + (dH / Sh) ** 2 + Rt * (dC / Sc) * (dH / Sh))


def sample_patches(img_rgb, roi, rows, cols, inner=0.4):
    """在 roi(x,y,w,h) 内按 rows×cols 网格采样, 每块取中心 inner 比例区域的均值。
    返回 (rows*cols, 3) 的 uint8 RGB。"""
    x, y, w, h = [int(v) for v in roi]
    sub = np.asarray(img_rgb)[y:y + h, x:x + w]
    cw, ch = w / cols, h / rows
    out = []
    for r in range(rows):
        for c in range(cols):
            x0 = int((c + 0.5 - inner / 2) * cw)
            x1 = int((c + 0.5 + inner / 2) * cw)
            y0 = int((r + 0.5 - inner / 2) * ch)
            y1 = int((r + 0.5 + inner / 2) * ch)
            patch = sub[y0:y1, x0:x1]
            out.append(patch.reshape(-1, 3).mean(axis=0))
    return np.array(out, dtype=np.uint8)


class CCResult:
    def __init__(self, ref_lab, meas_lab, meas_rgb):
        self.ref_lab = np.asarray(ref_lab)
        self.meas_lab = np.asarray(meas_lab)
        self.meas_rgb = np.asarray(meas_rgb)
        self.de76 = delta_e76(self.ref_lab, self.meas_lab)
        self.dc76 = delta_c76(self.ref_lab, self.meas_lab)
        self.de00 = delta_e2000(self.ref_lab, self.meas_lab)

    @property
    def mean_e00(self):
        return float(self.de00.mean())

    @property
    def mean_e76(self):
        return float(self.de76.mean())

    @property
    def mean_c76(self):
        return float(self.dc76.mean())

    @property
    def max_e00(self):
        return float(self.de00.max())

    @property
    def wb_error(self):
        """白平衡误差代理口径: 灰块(末行) ΔE2000 均值。经验对照, 非 Imatest 原文。"""
        gray = [i for i in GRAY_IDS if i < len(self.de00)]
        return float(self.de00[gray].mean()) if gray else float("nan")


GRAY_IDS = list(range(18, 24))


def analyze(img_rgb, roi, ref_lab, rows, cols, inner=0.4):
    rgb = sample_patches(img_rgb, roi, rows, cols, inner)
    lab = srgb_to_lab(rgb)
    return CCResult(ref_lab, lab, rgb)


def analyze_rects(img_rgb, patch_rects, ref_lab, inner=0.5):
    """按显式色块矩形采样(自动识别路径)。patch_rects: [(x,y,w,h)]"""
    out = []
    for (x, y, w, h) in patch_rects:
        x0 = int(x + w * (0.5 - inner / 2)); x1 = int(x + w * (0.5 + inner / 2))
        y0 = int(y + h * (0.5 - inner / 2)); y1 = int(y + h * (0.5 + inner / 2))
        patch = np.asarray(img_rgb)[y0:y1, x0:x1]
        out.append(patch.reshape(-1, 3).mean(axis=0) if patch.size else np.zeros(3))
    rgb = np.array(out, dtype=np.uint8)
    return CCResult(ref_lab, srgb_to_lab(rgb), rgb)
