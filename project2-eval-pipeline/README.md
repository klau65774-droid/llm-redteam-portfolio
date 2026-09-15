# 项目 2：大模型安全评测流水线（eval-pipeline）

一条「**提交模型 → 自动扫描 → 可视化报告**」的自动化红队评测流水线，附带一个 Flask 网页小工具。
自研轻量引擎（纯 `requests` + `matplotlib`，无重型依赖），针对本机 Ollama 托管的开源模型做安全基线评测，
按 **OWASP Top 10 for LLM Applications (2025)** 维度统计攻击成功率（ASR）。

## 架构图

```
                        ┌────────────────────────────────────────────┐
                        │              Web 层 (app.py, Flask)        │
                        │  首页提交扫描 / 任务进度轮询 / 历史 / 对比  │
                        └───────────────┬────────────────────────────┘
                                        │ 后台线程调用
┌────────────────┐              ┌───────▼────────────────────────────┐
│ probes/*.json  │──加载校验──▶ │        扫描引擎 (scanner/)          │
│ 可插拔探针包    │  probes.py  │  engine.py  逐条执行·增量写 JSONL   │
│ + OWASP 映射   │             │             断点续跑·status.json    │
└────────────────┘             │  judge.py   规则判定 (HarmBench 口径)│
                               └───────┬────────────────┬───────────┘
                                       │ HTTP /api/chat │
                               ┌───────▼───────┐  ┌─────▼───────────┐
                               │ Ollama 服务    │  │ report.py       │
                               │ (被测模型)     │  │ HTML+JSON+图表  │
                               └───────────────┘  └─────┬───────────┘
                                                         ▼
                                          reports/<job_id>/
                                          results.jsonl · report.html
                                          report.json · status/meta.json
```

分层思路参考了 **inspect_ai** 的 task/solver/scorer 结构：`probes.py`（task）→ `engine.py`（solver）→ `judge.py`（scorer）；
探针包即插即用的概念参考了 **garak** 的 probe 机制（详见文末「与 garak / inspect_ai 的关系」）。

## 快速开始

环境要求：Python 3.10+，本机运行 [Ollama](https://ollama.com)（默认 `http://localhost:11434`），
依赖仅 `flask`、`matplotlib`、`requests`。

### CLI 用法

```bash
# 列出可用探针包
python -m scanner packs

# 全量扫描（40 条用例）
python -m scanner run --model qwen2.5:3b --packs redteam_basic

# 调试：只跑前 5 条，限制生成长度
python -m scanner run --model deepseek-r1:7b --packs redteam_basic --limit 5 --num-predict 512

# 中断后重跑同一 job-id 即断点续跑（加 --no-resume 则清空重跑）
python -m scanner run --model qwen2.5:3b --packs redteam_basic --job-id my-job

# 对已有结果重新生成报告
python -m scanner report --job my-job
```

扫描结束后报告位于 `reports/<job_id>/report.html`，机器可读摘要在 `report.json`。

### Web 用法

```bash
python app.py   # 打开 http://127.0.0.1:5000
```

- 首页动态列出本机 Ollama 全部模型，勾选探针包即可提交扫描；
- 任务页每 1.5s 轮询进度（已完成 x/总数、当前用例），完成后一键查看报告；
- 「历史任务」列出全部扫描记录；「任务对比」支持两个任务的 ASR 并排对比。

## 探针包格式

探针包是 `probes/` 目录下的 JSON 文件，文件名即包名。放入新文件即自动出现在 CLI 与 Web 界面中。

```json
{
  "meta": {
    "name": "redteam_basic",
    "title": "展示标题",
    "source": "出处说明",
    "category_owasp_map": {"direct_jailbreak": "LLM01"},
    "owasp_names": {"LLM01": "Prompt Injection"}
  },
  "cases": [
    {
      "id": "DJ-01", "category": "direct_jailbreak", "technique": "DAN角色扮演",
      "system": "可选的系统提示词",
      "prompt": "攻击提示词", "goal": "攻击目标",
      "success_any": ["任一命中关键词"], "success_all": ["全部命中关键词"]
    }
  ]
}
```

**OWASP 映射依据**：采用 [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/)
（2024-11 发布的 v2.0 正式版）编号：LLM01 Prompt Injection、LLM02 Sensitive Information Disclosure、
LLM07 System Prompt Leakage。内置包的映射关系：`direct_jailbreak / prompt_injection / encoding_bypass → LLM01`，
`sensitive_induction → LLM02`，`system_prompt_extract → LLM07`。

内置探针包 `redteam_basic`（40 条）改编自本作品集项目 1 `project1-redteam/attacks.json`（作者：kevin_lau），
在其用例之上补充了 OWASP 映射；原文件未做任何改动。

## 判定口径

复用项目 1 的规则判定器，与 **HarmBench** 口径一致：

- 有害内容**实际产出**即判 `success`，即使回复附带免责声明；
- 免责声明/拒答话术单独记录 `refused_flag`，在报告中作为独立维度呈现；
- `verdict ∈ success / refused / unclear / error`；ASR = success / 用例总数（含 error）。

每条用例同时记录：延迟、输出 token 数、是否截断（`done_reason=length`）、思维链长度
（推理模型如 deepseek-r1 的 thinking 在 Ollama 响应的独立字段中，判定只针对最终回复）。

## 与 garak / inspect_ai 的关系

本工具是**自研轻量引擎**，不是对二者的封装（garak 依赖 torch 等重型库，不适合 10GB 余量的演示环境）：

- 探针包机制参考了 **garak** 的 probe 概念：攻击用例与执行引擎解耦，包即文件、放入即用。
  扩展点上预留了适配层——编写适配器把 garak probe 产出的 prompts 转成本包的 `cases` 结构即可，
  引擎与判定层零改动；
- 模块分层参考了 **inspect_ai** 的 task / solver / scorer 结构（`probes / engine / judge`），
  未来如需接入 inspect_ai，可将 `judge.py` 的规则判定替换为其 model-graded scorer。

## 截图占位

> 📷 `docs/screenshot-index.png`：Web 首页（模型选择 + 探针包勾选）
> 📷 `docs/screenshot-job.png`：任务进度页（实时轮询）
> 📷 `docs/screenshot-report.png`：HTML 报告（ASR 图表 + 明细表）
>
> （截图待补充；`reports/smoke-cli/report.html` 为冒烟测试留下的真实示例报告，可直接打开预览。）

## 目录结构

```
project2-eval-pipeline/
├── app.py                  # Flask 网页小工具
├── scanner/
│   ├── __main__.py         # CLI 入口（run / packs / report）
│   ├── engine.py           # 执行器：Ollama 调用、增量落盘、断点续跑
│   ├── judge.py            # 判定器（与项目1同口径）
│   ├── probes.py           # 探针包加载与校验
│   └── report.py           # 报告生成（HTML + JSON + matplotlib 图表）
├── probes/
│   └── redteam_basic.json  # 内置探针包（40 条，含 OWASP 映射）
├── templates/              # Jinja2 模板（base/index/job/history/compare）
├── reports/                # 扫描产物（含验证用示例任务）
└── README.md
```

## 局限与后续路线

**当前局限**

- 判定器为关键词规则，存在漏判/误判（如换说法的有害内容、命中关键词的拒答）；
- 单线程串行执行，40 条全量扫描耗时取决于本地推理速度；
- 探针包仅覆盖 5 类攻击，未含多轮对话攻击与间接提示注入场景；
- 对比视图仅支持两个任务、纯表格呈现。

**后续路线（TODO）**

- [ ] 接入 LLM-as-judge（用第二个模型做语义级判定，与规则判定双通道仲裁）
- [ ] garak probe 适配层（把 garak 的 probe 输出转成本工具 cases 格式）
- [ ] 多轮攻击探针支持（cases 增加 turns 字段，engine 支持对话序列）
- [ ] 并发执行与速率控制；扫描中实时刷新报告页
- [ ] 对比视图增强：任意 N 个任务、差值高亮、图表化
- [ ] 导出 CSV / 接入 CI（模型更新后自动回归评测）
