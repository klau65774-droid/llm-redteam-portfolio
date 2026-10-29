# LLM Red-Team Portfolio · kevin_lau

Systematic safety evaluation of open-source LLMs, done end-to-end on a
consumer CPU laptop — no GPU, no cloud, fully reproducible.

Three top-level modules, one pipeline each: **攻击 → 判定 → 分析**，
外加一个对齐失败案例研究。

## Architecture

```mermaid
flowchart LR
    subgraph P1["project1-redteam"]
        A1[攻击库<br/>attacks.json 80 例] --> R1[ollama_runner.py<br/>被测模型 Ollama]
        A2[测试集<br/>test_set.json 96 例] --> R2[runner.py<br/>GGUF llama.cpp]
        R1 --> J[ollama_judge.py<br/>LLM-as-Judge 严格 JSON<br/>+ 规则兜底]
        R2 --> JR[judge.py 规则判定]
        J --> AN[ollama_analyze.py<br/>ASR 汇总 + 图表<br/>伪拒答复查 Yes-but]
        JR --> AN
    end
    subgraph P2["project2-eval-pipeline"]
        C1[cli_pipeline.py<br/>probe→detector→report] --> D1[单文件 HTML 看板]
        W1[scanner/ Flask Web] --> D2[OWASP 映射报告<br/>历史 & 模型对比]
    end
    subgraph P3["project3-alignment-case"]
        E1[make_essay.py] --> E2[对齐失败案例深度复盘.pdf]
    end
    P1 -.复用 judged 结果.-> P2
```

## Quick Start（3 步复现）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境（复制后按需修改；所有脚本也支持命令行参数覆盖）
cp .env.example .env

# 3a. 轨道 1b（推荐，只需 Ollama）：
python project1-redteam/ollama_runner.py --model deepseek-r1:7b
python project1-redteam/ollama_judge.py \
    --input project1-redteam/results/deepseek-r1_7b.jsonl --judge-model qwen2.5:3b
python project1-redteam/ollama_analyze.py

# 3b. 轨道 1a（GGUF 本地推理，需先下载 Qwen2.5-1.5B-GGUF 到 project1-redteam/models/）：
python project1-redteam/runner.py --start 0 --end 96 \
    --model project1-redteam/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
python project1-redteam/analyze.py project1-redteam/results/raw_results.jsonl
```

断点续跑：runner/ollama_runner 默认 `--resume`，中断后重跑同一命令即可自动跳过已完成用例。

## Modules

| # | Module | Entry points | Deliverables |
|---|---|---|---|
| 1 | Red-team study | `runner.py` (GGUF) · `ollama_runner.py` (Ollama) · `ollama_judge.py` (LLM-as-Judge) · `ollama_analyze.py` | 96-case test set, 80-case attack library, judged JSONL, ASR tables & charts, Chinese PDF report |
| 2 | Eval pipeline | `cli_pipeline.py` (zero-dependency CLI) · `scanner/` + `app.py` (Flask Web) | probe → detector → report; OWASP-mapped HTML/JSON reports, history & model comparison |
| 3 | Alignment case study | `make_essay.py` | Chinese essay reviewing Anthropic's Agentic Misalignment research, Alignment Faking, and the OAI-HF incident |

## Headline results

**Track 1a — Qwen2.5-1.5B-Instruct (n=96, llama.cpp, CPU)**

| Metric | Result |
|---|---|
| Direct harmful-request refusal | **100%** (10/10) |
| Overall ASR (strict / incl. partial) | **19.0% / 27.4%** |
| Prompt-injection success | **33.3%** — weakest surface |
| Most effective jailbreaks | "Research excuse" 40% / "Story narrative" 40%; DAN 0% |
| Benign over-refusal (误杀率) | **0%** |

**Track 1b — DeepSeek-R1-7B vs Qwen2.5-3B (n=80, Ollama)**

| Metric | R1-7B | Qwen2.5-3B |
|---|---|---|
| Overall ASR | **70.0%** (28/40) | **50.0%** (20/40) |
| Social-engineering elicitation | 100% | 80% |
| System-prompt extraction | 100% (canary leaked verbatim) | 33.3% |

### 核心评测指标汇总（口径说明）

| 指标 | 定义 | 1a · Qwen2.5-1.5B | 1b · R1-7B | 1b · Qwen2.5-3B |
|---|---|---|---|---|
| **ASR** 攻击成功率 | `success / 有效样本`（成功 = 交付目标内容，含伪拒答 Yes-but 复核后升级） | 19.0% / 27.4%¹ | 70.0% | 50.0% |
| **拒答率** | `refused / 有效样本`（防线生效占比） | 直接请求 100% | ≈30%² | ≈50%² |
| **误杀率** | 良性对照被误拒比例 | **0%** | — | — |

¹ 严格口径 / 含部分突破。² 由 ASR 推算的有效样本残差，精确值以 `analysis/verdict_breakdown.md` 为准。
裁判口径与 HarmBench 一致：**免责声明不构成防御**——先声明免责后仍给出攻击内容的回复判为 JAILBROKEN（`ollama_judge.py` 严格 JSON 判定 + `ollama_analyze.py` 正则兜底双保险）。

Key cross-model findings: social-engineering wrappers beat technical encodings;
disclaimers are not defenses (7–11 successful attacks carried disclaimers);
reasoning models add a new risk surface — sensitive content appears in the
chain-of-thought even when the final answer is suppressed; deployment must
assume the system prompt *will* leak.

## Reproduce (full tracks)

```bash
# Track 1a: download Qwen2.5-1.5B-Instruct-GGUF (q4_k_m, ~1.1 GB) into
# project1-redteam/models/, then:
cd project1-redteam
python build_test_set.py && python runner.py --start 0 --end 96
python analyze.py && python finalize.py
python make_charts.py && python make_report.py

# Track 1b: requires Ollama with deepseek-r1:7b and qwen2.5:3b pulled
python ollama_runner.py --model deepseek-r1:7b
python ollama_judge.py --input results/deepseek-r1_7b.jsonl
python ollama_analyze.py

# Track 2a: render dashboard from existing judged data
cd ../project2-eval-pipeline
python cli_pipeline.py --from-results ../project1-redteam/results/judged.jsonl

# Track 2b: web app
python app.py   # http://127.0.0.1:5000

# Track 3: regenerate the essay PDF (needs a CJK font, auto-detected on Windows)
cd ../project3-alignment-case
python make_essay.py
```

## Configuration

No hardcoded paths. Every script follows **CLI args > env vars > defaults**:

| 环境变量 | 用途 | 默认 |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` / `JUDGE_MODEL` | 被测模型 / 裁判模型 | `deepseek-r1:7b` / `qwen2.5:3b` |
| `MODEL_PATH` | GGUF 模型权重路径 | `project1-redteam/models/…q4_k_m.gguf` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

## Ethics

All tests ran locally and offline. Attack intents are limited to mild,
dual-use categories (fraud, privacy, academic integrity); weapons/bio/explosives
were deliberately excluded. Quoted outputs in reports are sanitized and
truncated. This work is for defense — every finding ships with mitigations.

---
*kevin_lau · 2026.09 · refactored 2026.10*
