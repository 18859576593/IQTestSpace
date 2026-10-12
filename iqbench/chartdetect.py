# -*- coding: utf-8 -*-
"""ColorChecker 色块自动识别 (经典CV, 纯numpy+cv2)。
思路: 下采样 → Canny+膨胀找闭合块 → 四边形/面积/密实度筛选 → 面积中位数带过滤
→ 中心点按 行(4)/列(6) 最大间隙聚类成网格 → 每格定位色块框。
返回 24 个矩形(原图坐标) + 每格是否实检到(缺格用网格中位尺寸推补, 标记=False)。
"""
import cv2
import numpy as np


def _dedupe(rects, iou_thr=0.4):
    """按面积从大到小去重叠。rects: [(x,y,w,h,area)]"""
    out = []
    for r in sorted(rects, key=lambda r: -r[4]):
        if all(_iou(r, k) < iou_thr for k in out):
            out.append(r)
    return out


def _iou(a, b):
    ax0, ay0, aw, ah = a[:4]
    bx0, by0, bw, bh = b[:4]
    ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / (a[4] + b[4] - inter)


def _split_1d(vals, n_groups):
    """按最大间隙把有序序列切成 n_groups 组。"""
    vals = sorted(vals)
    if len(vals) < n_groups:
        return None
    gaps = [(vals[i + 1] - vals[i], i) for i in range(len(vals) - 1)]
    cuts = sorted(i for _, i in sorted(gaps, reverse=True)[:n_groups - 1])
    groups, prev = [], 0
    for c in cuts:
        groups.append(vals[prev:c + 1])
        prev = c + 1
    groups.append(vals[prev:])
    return groups


def detect_patches(img_rgb, rows=4, cols=6):
    """返回 (patch_rects, ok_flags, n_found)。patch_rects 为原图坐标 (x,y,w,h)。
    n_found < rows*cols 时仍返回网格(缺格推补), 由调用方提示。"""
    h, w = img_rgb.shape[:2]
    scale = min(1.0, 1200.0 / max(h, w))
    small = cv2.resize(img_rgb, (int(w * scale), int(h * scale))) if scale < 1.0 else img_rgb
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    img_area = sh * sw
    cand = []
    for c in contours:
        a = cv2.contourArea(c)
        if a < 0.0003 * img_area or a > 0.08 * img_area:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        ar = cw / max(ch, 1)
        if not (0.35 < ar < 2.8):
            continue
        if a / (cw * ch) < 0.55:          # 密实度: 色块近矩形
            continue
        hull = cv2.convexHull(c)
        if a / max(cv2.contourArea(hull), 1) < 0.8:
            continue
        cand.append((x, y, cw, ch, a))
    if len(cand) < rows * cols * 0.7:      # 候选太少, 放弃
        return None, None, 0
    # 面积中位数带: 只留与典型色块同量级的(去外框/噪声)
    med = np.median([r[4] for r in cand])
    cand = [r for r in cand if 0.35 * med < r[4] < 3.0 * med]
    cand = _dedupe(cand)
    if len(cand) < rows * cols * 0.7:
        return None, None, 0

    rows_g = _split_1d([r[1] + r[3] / 2 for r in cand], rows)
    if rows_g is None:
        return None, None, 0
    # 每行内再按列切
    cells = {}
    allw, allh = [], []
    for ri, rowvals in enumerate(rows_g):
        rsel = [r for r in cand if abs(r[1] + r[3] / 2 - np.mean(rowvals)) < np.ptp(rowvals) / 2 + 1
                or (r[1] + r[3] / 2) in rowvals]
        cols_g = _split_1d([r[0] + r[2] / 2 for r in rsel], cols)
        if cols_g is None:
            return None, None, 0
        for ci, colvals in enumerate(cols_g):
            hit = [r for r in rsel if (r[0] + r[2] / 2) in colvals]
            if hit:
                best = max(hit, key=lambda r: r[4])
                cells[(ri, ci)] = best
                allw.append(best[2]); allh.append(best[3])
    if len(cells) < rows * cols * 0.75:
        return None, None, 0

    mw, mh = float(np.median(allw)), float(np.median(allh))
    rects, oks = [], []
    for ri in range(rows):
        for ci in range(cols):
            if (ri, ci) in cells:
                x, y, cw, ch, _ = cells[(ri, ci)]
                rects.append((int(x / scale), int(y / scale),
                              int(cw / scale), int(ch / scale)))
                oks.append(True)
            else:  # 缺格: 用该行/列邻居中位位置推补
                xs = [cells[k][0] for k in cells if k[0] == ri] or \
                     [cells[k][0] for k in cells if k[1] == ci]
                ys = [cells[k][1] for k in cells if k[1] == ci] or \
                     [cells[k][1] for k in cells if k[0] == ri]
                mx = np.median(xs) if xs else (ci + 0.5) * (mw * 1.15)
                my = np.median(ys) if ys else (ri + 0.5) * (mh * 1.15)
                rects.append((int(mx / scale), int(my / scale),
                              int(mw / scale), int(mh / scale)))
                oks.append(False)
    return rects, oks, sum(oks)
