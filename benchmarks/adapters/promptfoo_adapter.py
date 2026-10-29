# -*- coding: utf-8 -*-
"""Promptfoo 对标适配器 (Promptfoo Benchmark Adapter)

功能：
将本项目的攻击探针库（attacks.json / redteam_basic.json）转换为标准的 Promptfoo 测试配置 (promptfoo.yaml)。
支持使用 `npx promptfoo eval` 直接驱动多模型进行工业级横向复测，实现自研工具与成熟开源生态的双向打通。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.abspath(os.path.join(HERE, "..", "..", "project1-redteam", "attacks.json"))


def export_to_promptfoo_yaml(src_json: str, out_yaml: str, default_provider: str = "ollama:chat:qwen2.5:3b"):
    with open(src_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    lines = [
        "# Promptfoo Automated Evaluation Configuration",
        "# Generated from llm-redteam-portfolio benchmark probes",
        "# Run: npx promptfoo eval -c " + os.path.basename(out_yaml),
        "",
        "description: \"LLM Red-Team Portfolio Benchmark Probe Suite\"",
        "",
        "providers:",
        f"  - id: '{default_provider}'",
        "    config:",
        "      temperature: 0.7",
        "      seed: 42",
        "",
        "defaultTest:",
        "  options:",
        "    provider: true",
        "",
        "tests:",
    ]

    for c in cases:
        lines.append(f"  - description: '[{c['id']}] {c.get('technique', c.get('category', 'test'))}'")
        
        # 构造 prompt
        prompt_text = c['prompt'].replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'    vars:')
        lines.append(f'      input: "{prompt_text}"')
        if c.get("system"):
            sys_text = c['system'].replace('"', '\\"').replace('\n', '\\n')
            lines.append(f'      system: "{sys_text}"')

        # 构造断言：HarmBench / 安全拒绝断言
        lines.append('    assert:')
        # 1. 拒答检测 (not-contains 安全声明)
        lines.append('      - type: not-icontains-any')
        lines.append('        value:')
        for kw in c.get("success_any", []):
            lines.append(f'          - "{kw}"')
        # 2. 负向断言：不应包含关键载荷
        if c.get("success_all"):
            lines.append('      - type: not-icontains-all')
            lines.append('        value:')
            for kw in c["success_all"]:
                lines.append(f'          - "{kw}"')

    os.makedirs(os.path.dirname(os.path.abspath(out_yaml)), exist_ok=True)
    with open(out_yaml, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[promptfoo_adapter] 成功导出 {len(cases)} 条测试用例至 {out_yaml}")


def main():
    ap = argparse.ArgumentParser(description="转换红队测试集为 Promptfoo YAML 配置")
    ap.add_argument("--src", default=DEFAULT_SRC, help="输入的测试集 JSON")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "promptfoo_redteam.yaml"), help="输出的 YAML 文件路径")
    ap.add_argument("--provider", default="ollama:chat:qwen2.5:3b", help="默认测试的模型提供方")
    args = ap.parse_args()

    export_to_promptfoo_yaml(args.src, args.out, args.provider)


if __name__ == "__main__":
    main()
