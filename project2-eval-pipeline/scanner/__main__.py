# -*- coding: utf-8 -*-
"""CLI 入口：python -m scanner <command>

命令：
  run    --model <ollama模型> --packs redteam_basic [--limit N] [--num-predict M]
         [--job-id ID] [--no-resume]   执行扫描并生成报告
  packs                               列出可用探针包
  report --job <job目录>              对已有结果重新生成报告
"""
import argparse
import os
import sys

from . import probes as probes_mod
from .engine import run_scan
from .report import build_report

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"
)


def _fmt_progress(s: dict):
    print(f"\r[{s['state']}] {s['done']}/{s['total']} 当前: {s.get('current', '')}    ",
          end="", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scanner", description="大模型红队自动评测引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="执行扫描")
    p_run.add_argument("--model", required=True, help="Ollama 模型名，如 qwen2.5:3b")
    p_run.add_argument("--packs", required=True, help="探针包名，逗号分隔")
    p_run.add_argument("--limit", type=int, default=None, help="只跑前 N 条（调试用）")
    p_run.add_argument("--num-predict", type=int, default=512, help="最大生成 token 数")
    p_run.add_argument("--job-id", default=None, help="任务 ID（默认自动生成）")
    p_run.add_argument("--no-resume", action="store_true", help="不续跑，清空旧结果重跑")

    p_packs = sub.add_parser("packs", help="列出探针包")

    p_rep = sub.add_parser("report", help="重新生成报告")
    p_rep.add_argument("--job", required=True, help="job 目录或 job_id")

    args = ap.parse_args(argv)

    if args.cmd == "packs":
        for p in probes_mod.list_packs():
            print(f"- {p['name']}: {p['title']}（{p['n_cases']} 条）"
                  + (f"  [错误: {p['error']}]" if p.get("error") else ""))
        return 0

    if args.cmd == "run":
        pack_names = [s.strip() for s in args.packs.split(",") if s.strip()]
        from datetime import datetime
        job_id = args.job_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        job_dir = os.path.join(REPORTS_DIR, job_id)
        print(f"任务目录: {job_dir}")
        try:
            meta = run_scan(args.model, pack_names, job_dir,
                            limit=args.limit, num_predict=args.num_predict,
                            resume=not args.no_resume,
                            progress_cb=_fmt_progress)
        except probes_mod.ProbePackError as e:
            print(f"\n探针包错误: {e}", file=sys.stderr)
            return 2
        print("\n扫描完成，生成报告中…")
        summary = build_report(job_dir)
        print(f"总体 ASR: {summary['overall_asr'] * 100:.1f}%  "
              f"判定分布: {summary['verdict_counts']}")
        print(f"报告: {os.path.join(job_dir, 'report.html')}")
        return 0

    if args.cmd == "report":
        job_dir = args.job
        if not os.path.isdir(job_dir):
            job_dir = os.path.join(REPORTS_DIR, args.job)
        summary = build_report(job_dir)
        print(f"报告已重新生成: {os.path.join(job_dir, 'report.html')}")
        print(f"总体 ASR: {summary['overall_asr'] * 100:.1f}%")
        return 0


if __name__ == "__main__":
    sys.exit(main())
