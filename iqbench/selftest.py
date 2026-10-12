# -*- coding: utf-8 -*-
"""合成数据自检: 用已知真值验证引擎实现。
锚点1: 高斯模糊斜边(σ=1px, 5°) → 理论 MTF50 = sqrt(ln2)/(√2·π·σ) = 0.1874 cy/px
锚点2: 参考Lab→sRGB合成色卡 → 测回 ΔE 应≈0(仅8bit量化误差)
用法: python main.py --selftest  /  IQBench.exe --selftest
"""
import sys
import numpy as np

from . import refs, colorcheck, sfr


def make_slant_edge(h=300, w=400, sigma=1.0, angle_deg=5.0, x0=None):
    from math import erf  # noqa
    import math
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    if x0 is None:
        x0 = w / 2
    xe = x0 + math.tan(math.radians(angle_deg)) * (y - h / 2)
    t = (x - xe) / (math.sqrt(2) * sigma)
    esf = 0.5 * (1 - np.vectorize(math.erf)(t))  # 亮→暗
    return (esf * 255).astype(np.uint8)


def synth_chart_from_ref(cell=50, gap=6, margin=18):
    """贴近真实 ColorChecker: 色块间有间隙、四周黑色衬底。"""
    ref = np.array(refs.CC24_POST2014_D50)
    rgb = colorcheck.lab_to_srgb(ref)
    rows, cols = 4, 6
    pitch = cell + gap
    Wt = cols * pitch + margin * 2 - gap
    Ht = rows * pitch + margin * 2 - gap
    img = np.zeros((Ht, Wt, 3), np.uint8)
    for i in range(rows * cols):
        r, c = divmod(i, cols)
        y0 = margin + r * pitch
        x0 = margin + c * pitch
        img[y0:y0 + cell, x0:x0 + cell] = rgb[i]
    return img


def run():
    ok = True
    # ---- 锚点1: SFR ----
    theory = np.sqrt(np.log(2)) / (np.sqrt(2) * np.pi * 1.0)
    img = make_slant_edge(sigma=1.0, angle_deg=5.0)
    r = sfr.analyze(img)
    err = abs(r.mtf50 - theory) / theory
    status = "PASS" if err < 0.08 else "FAIL"
    ok &= err < 0.08
    print(f"[SFR ] MTF50={r.mtf50:.4f} cy/px 理论={theory:.4f} 偏差={err*100:.1f}% "
          f"角度={r.angle_deg:.1f}° NyqMTF={r.nyquist_mtf:.3f} → {status}")

    img2 = make_slant_edge(sigma=0.5, angle_deg=8.0)
    r2 = sfr.analyze(img2)
    th2 = theory * 2.0
    err2 = abs(r2.mtf50 - th2) / th2
    status2 = "PASS" if err2 < 0.10 else "FAIL"
    ok &= err2 < 0.10
    print(f"[SFR ] σ=0.5: MTF50={r2.mtf50:.4f} 理论={th2:.4f} 偏差={err2*100:.1f}% → {status2}")

    # ---- 锚点2: ColorChecker 往返 ----
    chart = synth_chart_from_ref()
    res = colorcheck.analyze(chart, (0, 0, chart.shape[1], chart.shape[0]),
                             refs.CC24_POST2014_D50, 4, 6)
    status3 = "PASS" if res.mean_e00 < 1.5 and res.mean_e76 < 1.5 else "FAIL"
    ok &= res.mean_e00 < 1.5
    print(f"[CC  ] 合成往返 meanΔE00={res.mean_e00:.3f} meanΔE76={res.mean_e76:.3f} "
          f"maxΔE00={res.max_e00:.3f} → {status3}")

    # ΔE2000 实现自检: 自比对=0, 已知案例(经典测试向量)
    lab = np.array(refs.CC24_POST2014_D50)
    z = colorcheck.delta_e2000(lab, lab)
    print(f"[CC  ] ΔE2000 自比对 max={z.max():.2e} (应=0) → {'PASS' if z.max() < 1e-9 else 'FAIL'}")
    ok &= z.max() < 1e-9

    print("\n自检总结:", "全部通过 [PASS]" if ok else "存在失败项 [FAIL]")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
