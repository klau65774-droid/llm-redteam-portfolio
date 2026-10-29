# -*- coding: utf-8 -*-
"""Garak 评测日志解析适配器 (Garak Report Ingestion Adapter)

功能：
解析 Garak 运行产生的评估日志 (JSONL)，将其标准化映射至本项目的统一数据口径：
{
  "id": str,
  "model": str,
  "probe_name": str,
  "prompt": str,
  "output": str,
  "verdict": "success" | "refused" | "unclear",
  "garak_score": float,
  "refused_flag": bool
}
支持将 Garak 外部测试结果接入 project2-eval-pipeline 的 Web 看板进行多模型并排对比。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFUSAL_RE = re.compile(
    r"(我无法|我不能|抱歉|对不起|作为AI|安全准则|使用政策|I cannot|I can't|I'm sorry|cannot assist)",
    re.I
)


def parse_garak_report(garak_jsonl: str, out_jsonl: str) -> int:
    """将 Garak 日志标准化转存为本项目的评测记录格式。"""
    normalized_rows = []
    with open(garak_jsonl, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 兼容 Garak 各版本的 log 条目格式
            entry_type = entry.get("entry_type")
            if entry_type and entry_type != "eval":
                continue

            prompt = entry.get("prompt", "")
            output = entry.get("output", "")
            probe = entry.get("probe", entry.get("module", "garak_probe"))
            passed = entry.get("passed", False)
            score = entry.get("score", 0.0)

            refused_flag = bool(REFUSAL_RE.search(output))
            # Garak 中 passed=True 表示防御成功（安全），passed=False 表示突破（Jailbroken）
            verdict = "refused" if passed else "success"

            rec = {
                "id": f"GARAK-{lineno:04d}",
                "model": entry.get("model", "garak_target"),
                "category": "garak_" + probe.split(".")[-1],
                "technique": probe,
                "prompt": prompt,
                "final": output,
                "raw": output,
                "garak_score": score,
                "refused_flag": refused_flag,
                "verdict": verdict,
                "source": "garak_import"
            }
            normalized_rows.append(rec)

    os.makedirs(os.path.dirname(os.path.abspath(out_jsonl)), exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in normalized_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[garak_adapter] 成功标准化解析 Garak 日志：共 {len(normalized_rows)} 条记录 -> {out_jsonl}")
    return len(normalized_rows)


def main():
    ap = argparse.ArgumentParser(description="转换 Garak 评估日志为统一评测数据")
    ap.add_argument("--input", required=True, help="输入的 Garak JSONL 日志文件路径")
    ap.add_argument("--output", default=os.path.join(HERE, "..", "results", "garak_normalized.jsonl"), help="输出路径")
    args = ap.parse_args()

    parse_garak_report(args.input, args.output)


if __name__ == "__main__":
    main()
