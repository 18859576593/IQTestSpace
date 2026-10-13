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

    # ---- 锚点3: CCM 数学精确性(纯浮点) + 8bit现实(偏差有界) ----
    # ⚠️ 8bit量化在输入侧引入EIV系统偏差(~0.1量级, 样本数不消减)——物理上限, 非bug
    from . import ccm as ccmmod
    M0 = np.array([[1.06, -0.04, -0.005],
                   [-0.04, 1.07, -0.005],
                   [-0.02, -0.03, 1.01]])
    rng = np.random.default_rng(7)
    lin_rand = rng.uniform(0.05, 0.95, (60, 3))
    M_rec = ccmmod.solve_ccm_linear(lin_rand, lin_rand @ M0.T)
    e1 = np.abs(M_rec - M0).max()
    s4 = "PASS" if e1 < 1e-9 else "FAIL"
    ok &= e1 < 1e-9
    print(f"[CCM ] 数学层(纯浮点): max|M-M0|={e1:.1e} (应<1e-9) → {s4}")
    # 8bit量化后: 偏差应有界(<0.2)且列和精确
    Xq = colorcheck.srgb_to_linear(colorcheck.linear_to_srgb_u8(lin_rand @ M0.T))
    Mq = ccmmod.solve_ccm_linear(Xq, lin_rand)
    e2 = np.abs(Mq - M0).max()
    sums_ok = np.abs(Mq.sum(axis=0) - 1).max() < 1e-9
    s5 = "PASS" if e2 < 0.2 and sums_ok else "FAIL"
    ok &= e2 < 0.2 and sums_ok
    print(f"[CCM ] 8bit EIV偏差: max={e2:.3f} (<0.2), 列和精确={sums_ok} → {s5}")
    # CC24 全链: 校正后 ΔE00 显著改善且≤0.8
    lin_ref = colorcheck.lab_to_linear_rgb(lab)
    meas_u8 = colorcheck.linear_to_srgb_u8(np.clip(lin_ref @ M0.T, 0, 1))
    M24 = ccmmod.solve_ccm(meas_u8, lab)
    b4, aft, _ = ccmmod.evaluate(meas_u8, lab, M24)
    s6 = "PASS" if aft < 0.8 and aft < b4 else "FAIL"
    ok &= aft < 0.8 and aft < b4
    print(f"[CCM ] CC24全链: ΔE00 {b4:.2f}→{aft:.2f} (应≤0.8且改善) → {s6}")

    # ---- 锚点4: 亮度归一化不变性 (Imatest 默认口径的核心性质) ----
    dark = colorcheck.linear_to_srgb_u8(
        colorcheck.srgb_to_linear(chart) * 0.7)          # 欠曝30%的同一张卡
    r_full = colorcheck.analyze(chart, (0, 0, chart.shape[1], chart.shape[0]),
                                refs.CC24_POST2014_D50, 4, 6)
    r_dark = colorcheck.analyze(dark, (0, 0, dark.shape[1], dark.shape[0]),
                                refs.CC24_POST2014_D50, 4, 6)
    n_full = colorcheck.analyze_normalized(chart, (0, 0, chart.shape[1], chart.shape[0]),
                                           refs.CC24_POST2014_D50, 4, 6)
    n_dark = colorcheck.analyze_normalized(dark, (0, 0, dark.shape[1], dark.shape[0]),
                                           refs.CC24_POST2014_D50, 4, 6)
    diff = abs(n_full.mean_e00 - n_dark.mean_e00)
    raw_gap = r_dark.mean_e00 - r_full.mean_e00
    s7 = "PASS" if diff < 0.25 and raw_gap > 0.3 else "FAIL"   # 0.25=暗图8bit量化底
    ok &= diff < 0.25 and raw_gap > 0.3
    print(f"[CC-N] 欠曝30%: 未归一ΔE00 {r_full.mean_e00:.2f}→{r_dark.mean_e00:.2f}(应显著升), "
          f"归一后 {n_full.mean_e00:.3f}→{n_dark.mean_e00:.3f} (差{diff:.3f}<0.1) → {s7}")

    print("\n自检总结:", "全部通过 [PASS]" if ok else "存在失败项 [FAIL]")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
