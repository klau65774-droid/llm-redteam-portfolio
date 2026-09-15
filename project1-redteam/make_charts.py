# -*- coding: utf-8 -*-
"""生成报告用图表"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
try:
    from daimon_runtime import setup_plot; setup_plot()
except Exception:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

INK, ACC, GRAY, GOLD = "#1a2332", "#8c1d2f", "#8a93a1", "#b98a2e"

# ---- 图1：四类攻击 ASR ----
fig, ax = plt.subplots(figsize=(7.2, 3.6))
cats = ["直接请求\n(基线)", "越狱包装", "提示注入", "敏感诱导"]
succ = [0, 18, 33.3, 25]
part = [0, 8, 25, 0]
x = np.arange(len(cats))
b1 = ax.bar(x, succ, 0.5, color=ACC, label="完全突破")
b2 = ax.bar(x, part, 0.5, bottom=succ, color=GOLD, label="部分突破")
for i, (s, p) in enumerate(zip(succ, part)):
    tot = s + p
    ax.text(i, tot + 1.2, f"{tot:.0f}%", ha="center", fontsize=11,
            fontweight="bold", color=INK)
ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=10)
ax.set_ylabel("攻击成功率 (%)", fontsize=10)
ax.set_ylim(0, 45)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_title("四类攻击手法的成功率（n=84，良性对照过度拒答率 0%）", fontsize=11, color=INK)
fig.tight_layout()
fig.savefig("report/chart1_asr.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# ---- 图2：越狱五模板成功率 ----
fig, ax = plt.subplots(figsize=(7.2, 3.4))
tmpls = ["DAN\n开发者模式", "反向诱导\n禁忌清单", "小说角色\n扮演", "故事分步\n叙事", "学术研究\n借口"]
succ = [0, 0, 10, 40, 40]
part = [0, 10, 0, 20, 10]
x = np.arange(len(tmpls))
ax.bar(x, succ, 0.5, color=ACC, label="完全突破")
ax.bar(x, part, 0.5, bottom=succ, color=GOLD, label="部分突破")
for i, (s, p) in enumerate(zip(succ, part)):
    if s + p:
        ax.text(i, s + p + 1.2, f"{s+p:.0f}%", ha="center", fontsize=10,
                fontweight="bold", color=INK)
ax.set_xticks(x); ax.set_xticklabels(tmpls, fontsize=9.5)
ax.set_ylabel("攻击成功率 (%)", fontsize=10)
ax.set_ylim(0, 55)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, fontsize=9)
ax.set_title("五种越狱模板的有效性对比（每模板 n=10）", fontsize=11, color=INK)
fig.tight_layout()
fig.savefig("report/chart2_templates.png", dpi=160, bbox_inches="tight")
plt.close(fig)

print("charts ok")
