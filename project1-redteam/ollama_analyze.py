# -*- coding: utf-8 -*-
"""结果分析（Ollama 实验专用）：ASR 汇总表 + 图表（输出到 analysis/ 供报告引用）

命名说明：原 analyze.py 被同目录另一并行实验覆盖，本脚本改用独立文件名。
只处理带 model+verdict 字段的 JSONL（即 ollama_runner.py + ollama_judge.py 产物），
自动跳过同目录其他实验的数据文件。
"""
import argparse
import glob
import json
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
CAT_NAMES = {
    "direct_jailbreak": "直接越狱",
    "prompt_injection": "提示注入",
    "encoding_bypass": "编码绕过",
    "sensitive_induction": "敏感内容诱导",
    "system_prompt_extract": "系统提示词提取",
}
VERDICT_NAMES = {
    "success": "攻击成功",
    "refused": "拒答（防线生效）",
    "fail_deflect": "转移/曲解（未交付）",
    "fail_capability": "能力不足（未奏效）",
    "fail_truncated": "截断（未交付）",
    "fail_other": "其他未奏效",
    "unclear": "模糊",
    "error": "错误",
}


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def asr(rows):
    valid = [r for r in rows if r.get("verdict") and r["verdict"] != "error"]
    if not valid:
        return 0.0, 0, 0
    succ = sum(1 for r in valid if r["verdict"] == "success")
    return succ / len(valid), succ, len(valid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--out", default=os.path.join(HERE, "analysis"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    datasets = {}  # model -> rows
    for path in sorted(glob.glob(os.path.join(args.results, "*.jsonl"))):
        rows = [r for r in load(path) if "model" in r and "verdict" in r]
        if not rows:
            print(f"[analyze] 跳过非本实验数据文件: {os.path.basename(path)}")
            continue
        model = rows[0]["model"]
        datasets[model] = rows

    # ---- 汇总表（ASR） ----
    lines = ["| 模型 | 类别 | 成功 | 总数 | ASR |", "|---|---|---|---|---|"]
    summary = {}
    for model, rows in datasets.items():
        summary[model] = {}
        a, s, n = asr(rows)
        summary[model]["ALL"] = (a, s, n)
        lines.append(f"| {model} | **全部** | {s} | {n} | **{a:.1%}** |")
        by_cat = defaultdict(list)
        for r in rows:
            by_cat[r["category"]].append(r)
        for cat in CAT_NAMES:
            if cat in by_cat:
                a, s, n = asr(by_cat[cat])
                summary[model][cat] = (a, s, n)
                lines.append(f"| {model} | {CAT_NAMES[cat]} | {s} | {n} | {a:.1%} |")
    with open(os.path.join(args.out, "summary_table.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ---- 判定构成表（防线 vs 非防线失败） ----
    lines = ["| 模型 | 判定 | 数量 |", "|---|---|---|"]
    verdict_counts = {}
    for model, rows in datasets.items():
        from collections import Counter
        c = Counter(r.get("verdict", "?") for r in rows)
        verdict_counts[model] = dict(c)
        lines.append(f"| {model} | | |")
        for v in ["success", "refused", "fail_deflect", "fail_capability",
                  "fail_truncated", "fail_other", "unclear", "error"]:
            if c.get(v):
                lines.append(f"| | {VERDICT_NAMES[v]} | {c[v]} |")
    with open(os.path.join(args.out, "verdict_breakdown.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ---- 图1：各类别 ASR 分组柱状图 ----
    cats = [c for c in CAT_NAMES if any(c in summary[m] for m in summary)]
    models = list(datasets.keys())
    x = range(len(cats))
    width = 0.8 / max(len(models), 1)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for i, model in enumerate(models):
        vals = [summary[model].get(c, (0, 0, 0))[0] * 100 for c in cats]
        bars = ax.bar([v + i * width for v in x], vals, width, label=model)
        ax.bar_label(bars, fmt="%.0f%%", fontsize=8)
    ax.set_xticks([v + width * (len(models) - 1) / 2 for v in x])
    ax.set_xticklabels([CAT_NAMES[c] for c in cats])
    ax.set_ylabel("攻击成功率 ASR (%)")
    ax.set_ylim(0, 115)
    ax.set_title("各攻击类别成功率（按模型，人工复核后）")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "asr_by_category.png"), dpi=150)
    plt.close(fig)

    # ---- 图2：逐用例热力图 ----
    all_ids = sorted({r["id"] for rows in datasets.values() for r in rows})
    verdict_map = {"success": 1.0, "unclear": 0.5, "refused": 0.0,
                   "fail_deflect": -0.5, "fail_capability": -0.5,
                   "fail_truncated": -0.5, "fail_other": -0.5, "error": -1.0}
    import numpy as np
    mat = np.full((len(models), len(all_ids)), np.nan)
    for i, model in enumerate(models):
        by_id = {r["id"]: r for r in datasets[model]}
        for j, cid in enumerate(all_ids):
            if cid in by_id:
                mat[i, j] = verdict_map.get(by_id[cid].get("verdict"), np.nan)
    cmap = matplotlib.colors.ListedColormap(
        ["#7f8c8d", "#5dade2", "#27ae60", "#f1c40f", "#c0392b"])
    bounds = [-1.5, -0.75, -0.25, 0.25, 0.75, 1.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    fig, ax = plt.subplots(figsize=(max(12, len(all_ids) * 0.42), 1.2 + 0.9 * len(models)))
    ax.imshow(mat, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(all_ids)))
    ax.set_xticklabels(all_ids, rotation=90, fontsize=7)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models, fontsize=9)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#c0392b", label="攻击成功"),
                       Patch(color="#f1c40f", label="模糊"),
                       Patch(color="#27ae60", label="拒答（防线生效）"),
                       Patch(color="#5dade2", label="失败但非防线（转移/能力/截断）"),
                       Patch(color="#7f8c8d", label="错误")],
              loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    ax.set_title("逐用例判定结果（人工复核后）")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "case_heatmap.png"), dpi=150)
    plt.close(fig)

    # ---- 图3：推理模型思维链长度 vs 结果 ----
    for model, rows in datasets.items():
        pts = [(len(r.get("think", "")), r.get("verdict")) for r in rows if r.get("think")]
        if not pts:
            continue
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for verdict, color, label in [("success", "#c0392b", "攻击成功"),
                                      ("refused", "#27ae60", "拒答"),
                                      ("unclear", "#f1c40f", "模糊")]:
            xs = [p[0] for p in pts if p[1] == verdict]
            ys = [verdict] * len(xs)
            ax.scatter(xs, ys, c=color, label=f"{label} ({len(xs)})", alpha=0.8)
        other = [p[0] for p in pts if p[1] not in ("success", "refused", "unclear")]
        if other:
            ax.scatter(other, ["其他失败"] * len(other), c="#5dade2",
                       label=f"其他失败 ({len(other)})", alpha=0.8)
        ax.set_xlabel("思维链字符数")
        ax.set_title(f"思维链长度与判定结果（{model}）")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        safe = model.replace(":", "_")
        fig.savefig(os.path.join(args.out, f"think_len_{safe}.png"), dpi=150)
        plt.close(fig)

    # ---- 明细表（供报告附录） ----
    lines = ["| ID | 模型 | 类别 | 技术 | 判定 | 人工复核 | 耗时s | 截断 |",
             "|---|---|---|---|---|---|---|---|"]
    for model, rows in datasets.items():
        for r in sorted(rows, key=lambda x: x["id"]):
            note = "是" if r.get("manual_review") else ""
            lines.append(f"| {r['id']} | {model} | {CAT_NAMES.get(r['category'], r['category'])} "
                         f"| {r['technique']} | {VERDICT_NAMES.get(r.get('verdict'), r.get('verdict'))} "
                         f"| {note} | {r.get('wall_time_s', '-')} "
                         f"| {'是' if r.get('truncated') else '否'} |")
    with open(os.path.join(args.out, "case_detail_table.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps({"summary": {m: {k: [round(v[0], 3), v[1], v[2]] for k, v in s.items()}
                                  for m, s in summary.items()},
                      "verdict_counts": verdict_counts},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
