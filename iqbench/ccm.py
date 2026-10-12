# -*- coding: utf-8 -*-
"""CCM 色彩校正矩阵求解 (Imatest 口径: 线性RGB域最小二乘 + 列和=1保中性约束)。
关键工程点(来自泰芯标定实战的教训): 列和约束必须通过 KKT 消元进入 LSQ 联立求解,
不能先解无约束再事后归一——事后归一会偏离最优解。
输出矩阵 M: out_linear = M @ in_linear (3×3), 每列和=1 → 中性灰不变。
"""
import numpy as np

from .colorcheck import srgb_to_linear, lab_to_linear_rgb, linear_to_srgb_u8, CCResult, delta_e2000, srgb_to_lab


def solve_ccm_linear(X, Y):
    """核心求解: X,Y 均为 (N,3) 线性RGB。列和=1 约束经 KKT 联立消元。"""
    N = len(X)
    A = np.zeros((3 * N, 9))
    A[0::3, 0:3] = X   # out_R = M00·r + M01·g + M02·b
    A[1::3, 3:6] = X   # out_G
    A[2::3, 6:9] = X   # out_B
    b = Y.reshape(-1)
    C = np.zeros((3, 9))
    C[0, [0, 3, 6]] = 1
    C[1, [1, 4, 7]] = 1
    C[2, [2, 5, 8]] = 1
    K = np.block([[A.T @ A, C.T], [C, np.zeros((3, 3))]])
    rhs = np.concatenate([A.T @ b, np.ones(3)])
    return np.linalg.solve(K, rhs)[:9].reshape(3, 3)


def solve_ccm(meas_rgb_u8, ref_lab):
    """meas: 实测色块 RGB(8bit); ref: 参考 Lab(D50)。返回 3×3 float 矩阵(列和=1)。"""
    X = srgb_to_linear(meas_rgb_u8)
    Y = np.clip(lab_to_linear_rgb(np.asarray(ref_lab, dtype=float)), 0, None)
    return solve_ccm_linear(X, Y)


def apply_ccm(rgb_u8, M):
    """整图应用 CCM (线性域乘矩阵后回 sRGB)。"""
    lin = srgb_to_linear(np.asarray(rgb_u8, dtype=np.float64))
    out = lin @ M.T
    return linear_to_srgb_u8(out)


def to_q8(M):
    """泰芯 Q8 定点 (×256, 四舍五入)。注: 定点化后列和≈256, 板端核对用。"""
    Q = np.round(M * 256).astype(int)
    return Q


def evaluate(meas_rgb_u8, ref_lab, M):
    """校正前后误差对比: 返回 (before_de00_mean, after_de00_mean, corrected_rgb_u8)。"""
    before = CCResult(ref_lab, srgb_to_lab(meas_rgb_u8), meas_rgb_u8)
    corrected = apply_ccm(meas_rgb_u8, M)
    after = CCResult(ref_lab, srgb_to_lab(corrected), corrected)
    return before.mean_e00, after.mean_e00, corrected


def matrix_text(M, nd=4):
    return "\n".join("  ".join(f"{v:>8.{nd}f}" for v in row) for row in M)
