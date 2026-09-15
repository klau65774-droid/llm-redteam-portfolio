# -*- coding: utf-8 -*-
"""红队实验运行器（Ollama 版）：读取攻击库 -> 调用 Ollama -> 落盘 JSONL（断点续跑）

命名说明：本文件原名 runner.py，2026-09-15 发现另一并行代理在同目录写入了
基于 llama_cpp 的同名文件，为避免互相覆盖，Ollama 版改用此独立文件名。
"""
import argparse
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/api/chat"

THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def split_think(text: str):
    """分离推理模型的思维链与最终回复。"""
    think = ""
    m = THINK_RE.search(text or "")
    if m:
        think = m.group(0)
        final = THINK_RE.sub("", text).strip()
    else:
        final = (text or "").strip()
    return think, final


def query_ollama(model: str, system: str, prompt: str, num_predict: int,
                 temperature: float, seed: int, timeout: int = 600):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
            "seed": seed,
        },
    }
    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    wall = time.time() - t0
    msg = data.get("message", {})
    content = msg.get("content", "")
    think, final = split_think(content)
    # 新版 Ollama 将推理内容放在 message.thinking 独立字段
    if not think and msg.get("thinking"):
        think = msg["thinking"]
    return {
        "raw": content,
        "think": think,
        "final": final,
        "wall_time_s": round(wall, 1),
        "eval_count": data.get("eval_count"),
        "eval_duration_s": round(data.get("eval_duration", 0) / 1e9, 1),
        "truncated": data.get("done_reason") == "length",
    }


def done_ids(path: str):
    ids = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cases", default=os.path.join(HERE, "attacks.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--ids", default=None, help="逗号分隔，只跑指定用例")
    ap.add_argument("--categories", default=None, help="逗号分隔，只跑指定类别")
    ap.add_argument("--num-predict", type=int, default=768)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(args.cases, encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    only_ids = set(args.ids.split(",")) if args.ids else None
    only_cats = set(args.categories.split(",")) if args.categories else None
    if only_ids:
        cases = [c for c in cases if c["id"] in only_ids]
    if only_cats:
        cases = [c for c in cases if c["category"] in only_cats]

    model_safe = args.model.replace(":", "_").replace("/", "_")
    out = args.out or os.path.join(HERE, "results", f"{model_safe}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    skip = done_ids(out)
    todo = [c for c in cases if c["id"] not in skip]
    print(f"[runner] model={args.model} total={len(cases)} done={len(skip)} todo={len(todo)}",
          flush=True)

    with open(out, "a", encoding="utf-8") as fout:
        for i, case in enumerate(todo, 1):
            rec = {
                "id": case["id"],
                "category": case["category"],
                "technique": case["technique"],
                "model": args.model,
                "system": case.get("system", ""),
                "prompt": case["prompt"],
                "goal": case["goal"],
                "success_any": case.get("success_any", []),
                "success_all": case.get("success_all", []),
                "temperature": args.temperature,
                "seed": args.seed,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            try:
                r = query_ollama(args.model, case.get("system", ""), case["prompt"],
                                 args.num_predict, args.temperature, args.seed)
                rec.update(r)
                status = "ok"
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {e}"
                status = "error"
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
            print(f"[runner] {i}/{len(todo)} {case['id']} {status} "
                  f"{rec.get('wall_time_s', '-')}s", flush=True)
    print("[runner] finished ->", out, flush=True)


if __name__ == "__main__":
    sys.exit(main())
