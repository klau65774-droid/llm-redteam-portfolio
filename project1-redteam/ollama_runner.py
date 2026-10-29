# -*- coding: utf-8 -*-
"""红队实验运行器（Ollama 版）：读取攻击库 -> 调用 Ollama -> 落盘 JSONL（断点续跑）。

配置优先级：命令行参数 > 环境变量 > 默认值。
  --model        必填；Ollama 模型名（如 deepseek-r1:7b）
  --base-url     Ollama 服务地址，默认 $OLLAMA_BASE_URL（兼容旧变量 OLLAMA_HOST）
  --dataset      攻击库 JSON，默认 attacks.json
  --output       结果 JSONL，默认 results/<model_safe>.jsonl
  --resume       已完成的 id 自动跳过（默认开启）
  --max-retries  请求失败重试次数（默认 3，指数退避）
  --timeout      单请求超时秒数（默认 600）
"""
import argparse
import json
import logging
import os
import re
import sys
import time

import requests
from tqdm import tqdm

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ollama_runner")

HERE = os.path.dirname(os.path.abspath(__file__))
THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def default_base_url() -> str:
    """OLLAMA_BASE_URL 优先，兼容旧变量 OLLAMA_HOST；均带默认值。"""
    return (os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")


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


def query_ollama(base_url: str, model: str, system: str, prompt: str,
                 num_predict: int, temperature: float, seed: int,
                 timeout: int = 600, max_retries: int = 3,
                 retry_delay: float = 2.0) -> dict:
    """单次 chat 请求，带指数退避重试与连接前置检查。"""
    url = f"{base_url}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": num_predict,
                    "temperature": temperature, "seed": seed},
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            resp = requests.post(url, json=payload, timeout=timeout)
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
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = e
            log.warning("请求失败（第 %d/%d 次）: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    raise RuntimeError(f"Ollama 请求失败（重试 {max_retries} 次后放弃）: {last_err}")


def done_ids(path: str) -> set:
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


def check_server(base_url: str, timeout: float = 5.0) -> None:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(
            f"无法连接 Ollama（{base_url}）: {e}\n"
            "请先启动 Ollama 服务，或设置 OLLAMA_BASE_URL 指向远程实例。")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="红队实验运行器（Ollama 版），断点续跑")
    ap.add_argument("--model", default=os.getenv("OLLAMA_MODEL"),
                    help="Ollama 模型名（必填，或环境变量 OLLAMA_MODEL）")
    ap.add_argument("--base-url", default=default_base_url(),
                    help="Ollama 服务地址（或环境变量 OLLAMA_BASE_URL）")
    ap.add_argument("--dataset", "--cases",
                    default=os.getenv("ATTACKS_PATH", os.path.join(HERE, "attacks.json")),
                    help="攻击库 JSON（默认 attacks.json）")
    ap.add_argument("--output", default=os.getenv("OUTPUT_PATH"),
                    help="输出 JSONL（默认 results/<model>.jsonl）")
    ap.add_argument("--ids", default=None, help="逗号分隔，只跑指定用例")
    ap.add_argument("--categories", default=None, help="逗号分隔，只跑指定类别")
    ap.add_argument("--num-predict", type=int, default=768)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--retry-delay", type=float, default=2.0)
    ap.add_argument("--resume", dest="resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args()
    if not args.model:
        ap.error("请通过 --model 或环境变量 OLLAMA_MODEL 指定模型名")
    return args


def main() -> int:
    args = parse_args()
    check_server(args.base_url)

    with open(args.dataset, encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    only_ids = set(args.ids.split(",")) if args.ids else None
    only_cats = set(args.categories.split(",")) if args.categories else None
    if only_ids:
        cases = [c for c in cases if c["id"] in only_ids]
    if only_cats:
        cases = [c for c in cases if c["category"] in only_cats]

    model_safe = args.model.replace(":", "_").replace("/", "_")
    out = args.output or os.path.join(HERE, "results", f"{model_safe}.jsonl")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    skip = done_ids(out) if args.resume else set()
    todo = [c for c in cases if c["id"] not in skip]
    log.info("model=%s base=%s total=%d done=%d todo=%d -> %s",
             args.model, args.base_url, len(cases), len(skip), len(todo), out)
    if not todo:
        log.info("没有待跑用例，退出")
        return 0

    with open(out, "a", encoding="utf-8") as fout:
        for case in tqdm(todo, desc=f"attack[{args.model}]", unit="case"):
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
                r = query_ollama(args.base_url, args.model, case.get("system", ""),
                                 case["prompt"], args.num_predict, args.temperature,
                                 args.seed, timeout=args.timeout,
                                 max_retries=args.max_retries,
                                 retry_delay=args.retry_delay)
                rec.update(r)
                status = "ok"
            except Exception as e:  # noqa: BLE001 - 单条失败不应中断批次
                rec["error"] = f"{type(e).__name__}: {e}"
                status = "error"
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
            if status != "ok":
                log.warning("%s -> %s", case["id"], rec["error"])
    log.info("finished -> %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
