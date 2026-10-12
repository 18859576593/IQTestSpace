# IQBench — 图像客观指标测试工作台

桌面端图像客观质量测量工具（Windows），对标 Imatest 的 ColorChecker 与 SFR 模块做自研轻量替代。核心算法纯 numpy 实现，带合成数据锚点自检；界面 PySide6。

## 功能

### ColorChecker 色卡
- 24 块经典色卡（X-Rite post-2014 官方 Lab/D50 参考值，内嵌）
- 色彩链路：sRGB → 线性化(sRGB EOTF) → XYZ(D65) → **Bradford 色适应** → CIELAB(D50)
- 指标：**ΔE76 / ΔE2000 / ΔC76**（逐块+均值+最大值）、WB 误差代理（灰块 ΔE2000 均值）
- 可视化：参考色 vs 实测色对照色条、逐块明细表

### SFR 斜边锐度（ISO 12233 流程）
- 梯度质心定位边 → 最小二乘拟边角度 → 投影坐标 **8× 过采样**分箱 → ESF → LSF → FFT → MTF
- 指标：**MTF50 / MTF30 / MTF10 / Nyquist MTF**（cy/pixel；填像素间距后给 lp/mm）、边角度
- 可视化：ESF 曲线、MTF 曲线（带 MTF50 标线）

## 引擎验证锚点（`IQBench.exe --selftest`）

| 锚点 | 真值 | 实测 |
|---|---|---|
| 高斯模糊斜边 σ=1px, 5° → MTF50 | √ln2/(√2·π·σ) = 0.1874 cy/px | 0.1858（偏差 0.9%） |
| σ=0.5px, 8° → MTF50 | 0.3748 cy/px | 0.3627（3.2%） |
| 参考值 Lab→sRGB 合成色卡测回 | ΔE ≈ 0 | meanΔE00 = 0.30（8bit 量化底） |
| CIEDE2000 自比对 | = 0 | 0 |

## 使用

1. 双击 `dist/IQBench.exe`（或 `python main.py`）
2. 打开图像 → 在图上**拖拽框选 ROI**（色卡=整卡区域；SFR=包含一条近垂直斜边的小区域，约 5°）
3. 点「分析」；结果可存 CSV（reports/ 目录）

## 设计说明（反"AI 生成感"）

遵循 Refactoring UI（Wathan & Schabot）与 GNOME HIG 的克制路线：单一深青强调色 + 中性纸面底色、1px 扁平边框、无阴影/渐变/表情图标、系统字体（Segoe UI）+ 等宽数字（Consolas）、信息优先的紧凑布局——不用装饰填补，只用层级说话。

## 构建

```
build.bat        # PyInstaller → dist/IQBench.exe (单文件)
python main.py --selftest   # 引擎锚点自检(无界面)
```

## 结构

```
iqbench/
  refs.py         # X-Rite CC24 post-2014 参考值(D50) + Imatest JSON 加载器
  colorcheck.py   # 色彩引擎: sRGB→Lab(D50), ΔE76/2000/ΔC76, 色块采样
  sfr.py          # 斜边引擎: 梯度质心→分箱ESF→LSF→FFT→MTF
  selftest.py     # 合成数据锚点闭环
  ui/             # theme(QSS设计系统) / plot(QPainter自绘图表) / main_window
```

## 路线图

- [ ] 双帧时域噪声 σ（Δ(f1,f2)/√2，NR 验收主指标）
- [ ] 灰阶 OECF / Gamma 响应曲线
- [ ] 平场均匀性 + 坏点检测
- [ ] SQLite 结果库 + 按固件版本回归对比
- [ ] 多 ROI 批量 / 自动图卡定位（CNN 分类，参考 Imatest chart_identification 设计）

## 依赖

Python 3.14 · numpy · opencv-python · PySide6 · PyInstaller（打包）

## 声明

参考色卡数值为 X-Rite 公布的标准参考值。本项目为自研测量工具，与 Imatest 无关联；算法依据 ISO 12233 与 CIE 公开标准独立实现，经合成数据锚点验证。
