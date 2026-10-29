# -*- coding: utf-8 -*-
"""统计推断工具库：为 ASR 计算置信区间、标准误与模型间假设检验。

针对小样本（n=40 ~ 96）红队评测场景：
1. Wilson Score 置信区间（比普通正态近似 Wald 区间在极端比例与小样本下更可靠）；
2. Fisher 精确检验（两组 ASR 差异检验，无需大样本假设）；
3. 效应量（Odds Ratio 比值比与相对风险 Relative Risk）。
"""
import math
from typing import Tuple, Dict, Any

try:
    from scipy.stats import fisher_exact
except ImportError:
    fisher_exact = None


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """计算二项分布成功的 Wilson Score 置信区间。

    返回: (p_hat, lower_bound, upper_bound)
    """
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    if confidence == 0.95:
        z = 1.959963984540054
    elif confidence == 0.90:
        z = 1.6448536269514722
    elif confidence == 0.99:
        z = 2.5758293035489004
    else:
        # 默认回退 95%
        z = 1.959963984540054

    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2.0 * n)) / denom
    spread = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z**2 / (4.0 * (n**2))))
    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return p, lower, upper


def format_ci_str(k: int, n: int, confidence: float = 0.95) -> str:
    """格式化为带 95% CI 的字符串，如 '70.0% [54.6%, 81.9%]'。"""
    if n == 0:
        return "N/A"
    p, lo, hi = wilson_score_interval(k, n, confidence)
    return f"{p * 100:.1f}% [{lo * 100:.1f}%, {hi * 100:.1f}%]"


def compare_models_stats(k1: int, n1: int, k2: int, n2: int) -> Dict[str, Any]:
    """计算两个模型在某项指标上的统计学差异（Fisher 精确检验）。

    Model 1 组 vs Model 2 组
    """
    # 构造四格表：[[s1, f1], [s2, f2]]
    f1 = n1 - k1
    f2 = n2 - k2
    table = [[k1, f1], [k2, f2]]

    res = {
        "n1": n1, "k1": k1, "p1": k1 / n1 if n1 > 0 else 0.0,
        "n2": n2, "k2": k2, "p2": k2 / n2 if n2 > 0 else 0.0,
        "delta": (k1 / n1 - k2 / n2) if n1 > 0 and n2 > 0 else 0.0,
        "odds_ratio": None,
        "p_value_two_sided": None,
        "p_value_greater": None,
        "significant_p05": False,
    }

    if fisher_exact and n1 > 0 and n2 > 0:
        try:
            odds_ratio, p_two = fisher_exact(table, alternative="two-sided")
            _, p_greater = fisher_exact(table, alternative="greater")
            res["odds_ratio"] = round(odds_ratio, 3) if not math.isinf(odds_ratio) else "inf"
            res["p_value_two_sided"] = round(p_two, 4)
            res["p_value_greater"] = round(p_greater, 4)
            res["significant_p05"] = p_two < 0.05
        except Exception:
            pass

    return res
