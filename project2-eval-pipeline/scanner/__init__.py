# -*- coding: utf-8 -*-
"""scanner：大模型红队自动化评测引擎（自研轻量版）。

模块划分（参考 inspect_ai 的 task/solver/scorer 分层与 garak 的 probe 概念）：
- probes.py : 探针包加载（task 层，可插拔 probes/*.json）
- engine.py : 执行器（solver 层，调用 Ollama、增量落盘、断点续跑）
- judge.py  : 判定器（scorer 层，规则判定，口径与 HarmBench 一致）
- report.py : 报告生成（HTML + machine-readable JSON + matplotlib 图表）
"""

__version__ = "0.1.0"
