# -*- coding: utf-8 -*-
"""Flask 网页小工具：提交模型 → 后台扫描 → 可视化报告。

页面：
  /                首页：动态列出本机 Ollama 模型 + 探针包，提交扫描
  /job/<job_id>    任务页：轮询进度，完成后跳报告
  /report/<job_id> 查看 HTML 报告
  /history         历史任务列表
  /compare?a=&b=   两个任务的 ASR 对比视图

接口：
  POST /scan           创建扫描任务（后台线程执行）
  GET  /api/job/<id>   任务进度 JSON
"""
import json
import os
import threading
import uuid
from datetime import datetime

import requests
from flask import (Flask, abort, jsonify, redirect, render_template,
                   request, send_file, url_for)

from scanner import probes as probes_mod
from scanner.engine import OLLAMA_BASE, run_scan
from scanner.report import build_report, CATEGORY_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

app = Flask(__name__)
JOBS = {}          # job_id -> 内存态进度（引擎另写 status.json，双保险）
JOBS_LOCK = threading.Lock()


def _list_models() -> list:
    """从本机 Ollama /api/tags 动态获取模型列表；服务不可用时返回空列表。"""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def _scan_worker(job_id: str, model: str, packs: list,
                 limit: int, num_predict: int):
    job_dir = os.path.join(REPORTS_DIR, job_id)

    def cb(status):
        with JOBS_LOCK:
            JOBS[job_id].update(status)

    try:
        run_scan(model, packs, job_dir, limit=limit,
                 num_predict=num_predict, progress_cb=cb)
        build_report(job_dir)
        with JOBS_LOCK:
            JOBS[job_id]["state"] = "finished"
    except Exception as e:  # 线程内异常写入状态，前端可见
        with JOBS_LOCK:
            JOBS[job_id].update({"state": "failed", "error": str(e)})


@app.route("/")
def index():
    return render_template("index.html",
                           models=_list_models(),
                           packs=probes_mod.list_packs(),
                           ollama_base=OLLAMA_BASE)


@app.route("/scan", methods=["POST"])
def scan():
    model = request.form.get("model", "").strip()
    packs = request.form.getlist("packs")
    limit = request.form.get("limit", "").strip()
    num_predict = request.form.get("num_predict", "512").strip()
    if not model or not packs:
        abort(400, "必须选择模型和至少一个探针包")
    limit = int(limit) if limit.isdigit() else None
    num_predict = int(num_predict) if num_predict.isdigit() else 512
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    with JOBS_LOCK:
        JOBS[job_id] = {"state": "running", "done": 0, "total": 0,
                        "current": "", "model": model, "packs": packs}
    t = threading.Thread(target=_scan_worker,
                         args=(job_id, model, packs, limit, num_predict),
                         daemon=True)
    t.start()
    return redirect(url_for("job_page", job_id=job_id))


@app.route("/job/<job_id>")
def job_page(job_id):
    with JOBS_LOCK:
        mem = JOBS.get(job_id)
    return render_template("job.html", job_id=job_id, mem=mem)


@app.route("/api/job/<job_id>")
def job_api(job_id):
    with JOBS_LOCK:
        mem = JOBS.get(job_id)
    if mem:
        return jsonify(mem)
    # 服务重启后从磁盘恢复状态
    for fname in ("status.json", "meta.json"):
        path = os.path.join(REPORTS_DIR, job_id, fname)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return jsonify(json.load(f))
    abort(404)


def _job_summary(job_dir: str) -> dict:
    """读一个 job 目录的摘要（meta/report/status 三选其可用者）。"""
    job_id = os.path.basename(job_dir)
    info = {"job_id": job_id, "state": "unknown"}
    for fname, key in (("meta.json", "meta"), ("status.json", "status"),
                       ("report.json", "report")):
        path = os.path.join(job_dir, fname)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    info[key] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
    meta = info.get("meta", {})
    status = info.get("status", {})
    report = info.get("report", {})
    info.update({
        "model": meta.get("model") or report.get("model", "?"),
        "started_at": meta.get("started_at", ""),
        "finished_at": meta.get("finished_at", ""),
        "total": meta.get("total") or report.get("total", 0),
        "asr": report.get("overall_asr", meta.get("asr")),
        "state": status.get("state", "finished" if report else "unknown"),
        "has_report": os.path.isfile(os.path.join(job_dir, "report.html")),
    })
    return info


@app.route("/history")
def history():
    jobs = []
    if os.path.isdir(REPORTS_DIR):
        for name in sorted(os.listdir(REPORTS_DIR), reverse=True):
            d = os.path.join(REPORTS_DIR, name)
            if os.path.isdir(d):
                jobs.append(_job_summary(d))
    return render_template("history.html", jobs=jobs)


@app.route("/report/<job_id>")
def report_page(job_id):
    path = os.path.join(REPORTS_DIR, job_id, "report.html")
    if not os.path.isfile(path):
        abort(404, "报告尚未生成或任务不存在")
    return send_file(path)


@app.route("/compare")
def compare():
    a, b = request.args.get("a", ""), request.args.get("b", "")
    rows, errors = [], []
    for job_id in (a, b):
        if not job_id:
            continue
        path = os.path.join(REPORTS_DIR, job_id, "report.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                rows.append(json.load(f))
        else:
            errors.append(f"{job_id}: 无 report.json")
    # 收集全部类别与 OWASP 键，做并排对比
    cats = sorted({k for r in rows for k in r.get("by_category", {})})
    owasps = sorted({k for r in rows for k in r.get("by_owasp", {})})
    return render_template("compare.html", reports=rows, errors=errors,
                           cats=cats, owasps=owasps,
                           cat_labels=CATEGORY_LABELS, a=a, b=b)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
