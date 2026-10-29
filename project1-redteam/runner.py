# -*- coding: utf-8 -*-
"""红队测试运行器（llama.cpp / GGUF 版）：分批执行，断点续跑。

配置优先级：命令行参数 > 环境变量 > 默认值。
  --model    模型路径，默认 $MODEL_PATH（如 models/qwen2.5-1.5b-instruct-q4_k_m.gguf）
  --dataset  测试集，默认 prompts/test_set.json
  --output   结果 JSONL，默认 results/raw_results.jsonl
  --start/--end  测试集下标切片（替代旧的位置参数）
  --resume   已完成的 id 自动跳过（默认开启，--no-resume 关闭）
  --max-retries / --retry-delay  单条推理失败时的重试策略

所有本地路径均已移除，模型权重不入库（见 .gitignore 与 .env.example）。
"""
import argparse
import json
import logging
import os
import sys
import time

from tqdm import tqdm

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("runner")

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODEL = os.path.join(HERE, "models",
                             "qwen2.5-1.5b-instruct-q4_k_m.gguf")
DEFAULT_DATASET = os.path.join(HERE, "prompts", "test_set.json")
DEFAULT_OUTPUT = os.path.join(HERE, "results", "raw_results.jsonl")
MAX_TOKENS = 80


def load_done(path: str) -> set:
    """读取输出文件中已完成的 id 集合（自动容错损坏行）。"""
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    log.warning("跳过损坏行 %s:%d", path, lineno)
    return done


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="红队测试运行器（GGUF，CPU 可跑），结果逐条落盘可断点续跑")
    ap.add_argument("--model", default=os.getenv("MODEL_PATH", DEFAULT_MODEL),
                    help="GGUF 模型路径（或环境变量 MODEL_PATH）")
    ap.add_argument("--dataset", default=os.getenv("DATASET_PATH", DEFAULT_DATASET),
                    help="测试集 JSON（或环境变量 DATASET_PATH）")
    ap.add_argument("--output", default=os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT),
                    help="输出 JSONL（或环境变量 OUTPUT_PATH）")
    ap.add_argument("--start", type=int, default=0, help="切片起点下标（含）")
    ap.add_argument("--end", type=int, default=None, help="切片终点下标（不含）")
    ap.add_argument("--resume", dest="resume", action="store_true", default=True,
                    help="跳过输出文件中已完成的 id（默认开启）")
    ap.add_argument("--no-resume", dest="resume", action="store_false",
                    help="忽略已有结果，全部重跑")
    ap.add_argument("--max-retries", type=int, default=3,
                    help="单条推理失败最大重试次数")
    ap.add_argument("--retry-delay", type=float, default=2.0,
                    help="重试间隔秒数")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    args = ap.parse_args()
    if not os.path.exists(args.model):
        ap.error(f"模型文件不存在: {args.model}（请下载 GGUF 到 project1-redteam/models/ "
                 f"或设置 MODEL_PATH）")
    if not os.path.exists(args.dataset):
        ap.error(f"测试集不存在: {args.dataset}")
    return args


def run_one(llm, prompt: str, max_tokens: int, max_retries: int, retry_delay: float):
    """单条推理，带指数退避重试。返回 (response, ntok)。"""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=0.3, top_p=0.9)
            return r["choices"][0]["message"]["content"], r["usage"]["completion_tokens"]
        except Exception as e:  # noqa: BLE001 - 推理异常需逐条容错
            last_err = e
            log.warning("推理失败（第 %d/%d 次）: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    return f"[ERROR] {type(last_err).__name__}: {last_err}", 0


def main() -> int:
    args = parse_args()
    with open(args.dataset, encoding="utf-8") as f:
        test_set = json.load(f)
    batch = test_set[args.start:args.end]
    done = load_done(args.output) if args.resume else set()
    todo = [x for x in batch if x["id"] not in done]
    log.info("切片 [%s:%s] 共 %d 条，已完成 %d 条，待跑 %d 条",
             args.start, args.end, len(batch), len(batch) - len(todo), len(todo))
    if not todo:
        log.info("没有待跑用例，退出")
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    from llama_cpp import Llama  # 延迟导入，--help 时无需安装依赖
    llm = Llama(model_path=args.model, n_ctx=2048, n_threads=4,
                use_mlock=True, verbose=False)
    # warmup，消除首次加载偏慢
    llm.create_chat_completion(messages=[{"role": "user", "content": "hi"}],
                               max_tokens=4)

    with open(args.output, "a", encoding="utf-8") as out:
        for item in tqdm(todo, desc="runner", unit="case"):
            t0 = time.time()
            resp, ntok = run_one(llm, item["prompt"], args.max_tokens,
                                 args.max_retries, args.retry_delay)
            rec = dict(item)
            rec["response"] = resp
            rec["completion_tokens"] = ntok
            rec["seconds"] = round(time.time() - t0, 1)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            log.info("%s %s %dtok %.1fs | %s", item["id"], item["category"],
                     ntok, rec["seconds"], resp[:60].replace("\n", " "))
    log.info("完成 -> %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
