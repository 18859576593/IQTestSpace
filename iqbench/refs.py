# -*- coding: utf-8 -*-
"""色卡参考数据。默认内嵌 X-Rite ColorChecker Classic 24 块 post-2014 官方 Lab(D50) 值；
也支持加载 Imatest 格式的 ColorReferenceJSON。
出处: X-Rite 官方公布值(经由本机 Imatest 安装包 resources/ColorReferenceJSONs/
XRite_CC_24patch_post2014.json 核对), 参考白 D50。
"""
import json
import os

# X-Rite ColorChecker Classic (post Nov-2014), D50, L*a*b*
PATCH_NAMES = [
    "深肤", "浅肤", "蓝天", "树叶", "蓝花", "蓝绿",
    "橙", "紫蓝", "中红", "紫", "黄绿", "橙黄",
    "蓝", "绿", "红", "黄", "品红", "青",
    "白", "20%灰", "40%灰", "60%灰", "80%灰", "黑",
]
GRAY_INDICES = list(range(18, 24))  # 末行 6 块灰

CC24_POST2014_D50 = [
    [37.54, 14.37, 14.92], [64.66, 19.27, 17.5], [49.32, -3.82, -22.54],
    [43.46, -12.74, 22.72], [54.94, 9.61, -24.79], [70.48, -32.26, -0.37],
    [62.73, 35.83, 56.5], [39.43, 10.75, -45.17], [50.57, 48.64, 16.67],
    [30.1, 22.54, -20.87], [71.77, -24.13, 58.19], [71.51, 18.24, 67.37],
    [28.37, 15.42, -49.8], [54.38, -39.72, 32.27], [42.43, 51.05, 28.62],
    [81.8, 2.67, 80.41], [50.63, 51.28, -14.12], [49.57, -29.71, -28.32],
    [95.19, -1.03, 2.93], [81.29, -0.57, 0.44], [66.89, -0.75, -0.06],
    [50.76, -0.13, 0.14], [35.63, -0.46, -0.48], [20.64, 0.07, -0.46],
]


def load_imatest_json(path):
    """加载 Imatest ColorReferenceJSON, 返回 (rows,cols,L*a*b*列表) 或 None。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
        vals = d["colorReference"]["reference_values"]
        rows = d["colorReference"].get("rows", 0)
        cols = d["colorReference"].get("cols", 0)
        if vals and isinstance(vals[0], list) and len(vals[0]) >= 3:
            if not rows or not cols:
                cols = 6
                rows = max(1, len(vals) // cols)
            return rows, cols, [v[:3] for v in vals]
    except Exception:
        pass
    return None
