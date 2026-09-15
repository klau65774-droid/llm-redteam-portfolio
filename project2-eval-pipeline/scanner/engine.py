# -*- coding: utf-8 -*-
"""扫描引擎：调用 Ollama 逐条执行探针，判定并增量写 JSONL（支持断点续跑）。

产物（reports/<job_id>/ 下）：
- results.jsonl : 每行一条用例执行记录（增量追加，崩溃后可续跑）
- status.json   : 任务进度快照（CLI/Web 轮询共用）
- meta.json     : 任务元信息（模型、参数、探针包、起止时间）

推理模型（如 deepseek-r1）的思维链在 Ollama 响应的 message.thinking
独立字段中，与最终回复 message.content 分开记录；判定只针对最终回复。
"""
import json
import os
import time
from datetime import datetime

import requests

from .judge import judge_record
from .probes import collect_cases

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
DEFAULT_NUM_PREDICT = 512
DEFAULT_TIMEOUT = 180


def chat(model: str, prompt: str, system: str = None,
         num_predict: int = DEFAULT_NUM_PREDICT,
         timeout: int = DEFAULT_TIMEOUT) -> dict:
    """调用 Ollama /api/chat，返回统一结构（含耗时、token 数、是否截断）。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": num_predict},
    }
    t0 = time.time()
    try:
        r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # 网络/超时/服务错误统一记为 error，不中断扫描
        return {"final": "", "thinking": "", "error": f"{type(e).__name__}: {e}",
                "latency_s": round(time.time() - t0, 2),
                "output_tokens": 0, "truncated": False, "thinking_chars": 0}
    latency = time.time() - t0
    msg = data.get("message", {})
    thinking = msg.get("thinking", "") or ""
    return {
        "final": msg.get("content", "") or "",
        "thinking": thinking,
        "error": "",
        "latency_s": round(latency, 2),
        "output_tokens": data.get("eval_count", 0),
        "truncated": data.get("done_reason") == "length",
        "thinking_chars": len(thinking),
    }


def _write_json(path: str, obj: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # 原子替换，避免轮询方读到半截文件


def _load_done_ids(results_path: str) -> set:
    """读取已有 results.jsonl，返回已完成用例 id 集合（断点续跑依据）。"""
    done = set()
    if os.path.isfile(results_path):
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        continue
    return done


def run_scan(model: str, pack_names: list, job_dir: str,
             limit: int = None, num_predict: int = DEFAULT_NUM_PREDICT,
             probes_dir: str = None, resume: bool = True,
             progress_cb=None) -> dict:
    """执行一次完整扫描。返回汇总统计字典。

    progress_cb(status_dict) 在每条用例完成后回调（供 Web 实时进度）。
    """
    from .probes import DEFAULT_PROBES_DIR
    probes_dir = probes_dir or DEFAULT_PROBES_DIR
    os.makedirs(job_dir, exist_ok=True)
    results_path = os.path.join(job_dir, "results.jsonl")
    status_path = os.path.join(job_dir, "status.json")
    meta_path = os.path.join(job_dir, "meta.json")

    cases, packs_meta = collect_cases(pack_names, probes_dir)
    if limit:
        cases = cases[:limit]
    total = len(cases)

    done_ids = _load_done_ids(results_path) if resume else set()
    if not resume and os.path.isfile(results_path):
        os.remove(results_path)

    meta = {
        "job_id": os.path.basename(job_dir),
        "model": model,
        "packs": [m.get("name") for m in pack_names and packs_meta] or pack_names,
        "packs_detail": packs_meta,
        "limit": limit,
        "num_predict": num_predict,
        "ollama_base": OLLAMA_BASE,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
    }
    _write_json(meta_path, meta)

    status = {"state": "running", "total": total, "done": len(done_ids),
              "current": "", "updated_at": meta["started_at"]}
    _write_json(status_path, status)

    counts = {"success": 0, "refused": 0, "unclear": 0, "error": 0}
    with open(results_path, "a", encoding="utf-8") as out:
        for case in cases:
            if case["id"] in done_ids:
                continue
            status["current"] = case["id"]
            _write_json(status_path, status)
            resp = chat(model, case["prompt"], system=case.get("system"),
                        num_predict=num_predict)
            rec = {**case, **resp}
            rec["verdict"] = judge_record(rec)
            counts[rec["verdict"]] += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()  # 每条立即落盘，保证断点续跑粒度为单条用例
            status["done"] += 1
            status["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _write_json(status_path, status)
            if progress_cb:
                progress_cb(dict(status))

    # 汇总时把续跑前已完成的记录也计入
    if done_ids:
        with open(results_path, encoding="utf-8") as f:
            counts = {"success": 0, "refused": 0, "unclear": 0, "error": 0}
            for line in f:
                if line.strip():
                    v = json.loads(line).get("verdict", "unclear")
                    counts[v] = counts.get(v, 0) + 1

    meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
    meta["counts"] = counts
    n = sum(counts.values())
    meta["asr"] = round(counts["success"] / n, 4) if n else 0.0
    _write_json(meta_path, meta)
    status.update({"state": "finished",
                   "updated_at": meta["finished_at"]})
    _write_json(status_path, status)
    if progress_cb:
        progress_cb(dict(status))
    return meta
