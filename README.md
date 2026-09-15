# LLM Red-Team Portfolio · kevin_lau

Systematic safety evaluation of open-source LLMs, done end-to-end on a
consumer CPU laptop — no GPU, no cloud, fully reproducible.

Two experiment tracks + one engineering pipeline + one research essay:

| # | Project | Dir | Deliverables |
|---|---|---|---|
| 1a | Red-team study — Qwen2.5-1.5B (llama.cpp) | `project1-redteam/` | 96-case test set, judged dataset, 9-page Chinese report PDF, charts |
| 1b | Red-team study — DeepSeek-R1-7B vs Qwen2.5-3B (Ollama) | `project1-redteam/` (`REPORT.md`, `ollama_*.py`, `analysis/`) | 80 attacks across 2 models, cross-model comparison report, analysis charts |
| 2a | Lightweight pipeline (GGUF → HTML) | `project2-pipeline/` | Zero-dependency CLI (`probe → detector → report`), single-file interactive dashboard |
| 2b | Eval-pipeline web app (Ollama) | `project2-eval-pipeline/` | Flask web tool: submit model → auto-scan → OWASP-mapped HTML/JSON reports, pluggable probe packs, history & model comparison |
| 3 | Alignment-failure case reviews | `project3-alignment/`, `project3-alignment-case/` | Chinese essays reviewing Anthropic's Agentic Misalignment research, Alignment Faking, and the OAI-HF incident |

## Headline results

**Track 1a — Qwen2.5-1.5B-Instruct (n=96, llama.cpp, CPU)**

| Metric | Result |
|---|---|
| Direct harmful-request refusal | **100%** (10/10) |
| Overall ASR (strict / incl. partial) | **19.0% / 27.4%** |
| Prompt-injection success | **33.3%** — weakest surface |
| Most effective jailbreaks | "Research excuse" 40% / "Story narrative" 40%; DAN 0% |
| Benign over-refusal | 0% |

**Track 1b — DeepSeek-R1-7B vs Qwen2.5-3B (n=80, Ollama)**

| Metric | R1-7B | Qwen2.5-3B |
|---|---|---|
| Overall ASR | **70.0%** (28/40) | **50.0%** (20/40) |
| Social-engineering elicitation | 100% | 80% |
| System-prompt extraction | 100% (canary leaked verbatim) | 33.3% |

Key cross-model findings: social-engineering wrappers beat technical encodings;
disclaimers are not defenses (7–11 successful attacks carried disclaimers);
reasoning models add a new risk surface — sensitive content appears in the
chain-of-thought even when the final answer is suppressed; deployment must
assume the system prompt *will* leak.

## Reproduce

```bash
pip install llama-cpp-python matplotlib
# Track 1a: download Qwen2.5-1.5B-Instruct-GGUF (q4_k_m, ~1.1 GB) into
# project1-redteam/models/, then:
cd project1-redteam
python build_test_set.py && python runner.py 0 96
python analyze.py && python finalize.py
python make_charts.py && python make_report.py

# Track 1b: requires Ollama with deepseek-r1:7b and qwen2.5:3b pulled
python ollama_runner.py && python ollama_judge.py && python ollama_analyze.py

# Track 2a: render dashboard from existing judged data
cd ../project2-pipeline
python pipeline.py --from-results ../project1-redteam/results/judged.jsonl

# Track 2b: web app
cd ../project2-eval-pipeline
python app.py   # http://127.0.0.1:5000
```

## Ethics

All tests ran locally and offline. Attack intents are limited to mild,
dual-use categories (fraud, privacy, academic integrity); weapons/bio/explosives
were deliberately excluded. Quoted outputs in reports are sanitized and
truncated. This work is for defense — every finding ships with mitigations.

---
*kevin_lau · 2026.09*
