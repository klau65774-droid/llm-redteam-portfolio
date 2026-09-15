# -*- coding: utf-8 -*-
"""
红队测试运行器：分批执行，断点续跑
用法: python runner.py <start> <end>   （按 test_set.json 下标切片）
每条结果追加写入 results/raw_results.jsonl（已完成 id 自动跳过）
"""
import json, os, sys, time
from llama_cpp import Llama

MODEL = "models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
OUT = "results/raw_results.jsonl"
MAX_TOKENS = 80

def load_done():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    return done

def main(start, end):
    with open("prompts/test_set.json", encoding="utf-8") as f:
        test_set = json.load(f)
    batch = test_set[start:end]
    done = load_done()
    todo = [x for x in batch if x["id"] not in done]
    print(f"切片 [{start}:{end}] 共 {len(batch)} 条，待跑 {len(todo)} 条")
    if not todo:
        return

    llm = Llama(model_path=MODEL, n_ctx=2048, n_threads=4,
                use_mlock=True, verbose=False)
    # warmup，消除首次加载偏慢
    llm.create_chat_completion(messages=[{"role": "user", "content": "hi"}], max_tokens=4)

    with open(OUT, "a", encoding="utf-8") as out:
        for i, item in enumerate(todo, 1):
            t0 = time.time()
            try:
                r = llm.create_chat_completion(
                    messages=[{"role": "user", "content": item["prompt"]}],
                    max_tokens=MAX_TOKENS, temperature=0.3, top_p=0.9)
                resp = r["choices"][0]["message"]["content"]
                ntok = r["usage"]["completion_tokens"]
            except Exception as e:
                resp, ntok = f"[ERROR] {e}", 0
            rec = dict(item)
            rec["response"] = resp
            rec["completion_tokens"] = ntok
            rec["seconds"] = round(time.time() - t0, 1)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{i}/{len(todo)}] {item['id']} {item['category']} "
                  f"{ntok}tok {rec['seconds']}s | {resp[:40].replace(chr(10),' ')}...")

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
