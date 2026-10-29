# LLM Red-Team Portfolio · kevin_lau

Systematic safety evaluation of open-source LLMs & MCP Agents, done end-to-end on a
consumer CPU laptop — no GPU, no cloud, fully reproducible.

涵盖：**大模型离线红队评测 → 自动化扫描平台 → 对齐案例复盘 → MCP Agent 工具投毒实测 → 行业工具 (Garak/Promptfoo) 对标**。

## Architecture

```mermaid
flowchart TD
    subgraph P1["1. project1-redteam · 单模型与推理模型红队"]
        A1[结构化攻击库<br/>80+96 用例] --> R1[双引擎推理<br/>llama.cpp GGUF / Ollama]
        R1 --> J1[分层判定流水线<br/>规则初判 + 全量人工复核]
        J1 --> S1[统计推断模块<br/>Wilson 95% CI + Fisher 精确检验]
        J1 --> K1[裁判可靠性基准<br/>混淆矩阵 + Cohen's Kappa κ]
    end

    subgraph P2["2. project2-eval-pipeline · 自动化扫描平台"]
        C1[CLI 快速流水线<br/>probe → detector → report]
        W1[Flask Web 控制台<br/>动态加载探针 / 任务轮询]
        O1[OWASP LLM Top 10<br/>2025 正式版映射]
        C1 --> O1
        W1 --> O1
    end

    subgraph P4["4. project4-mcp-agent-security · Agent 安全与投毒评测"]
        M1[MCP 工具描述投毒<br/>Tool Description Poisoning]
        M2[工具返回间接注入<br/>Indirect Injection via Returns]
        M3[路由对抗降级攻击<br/>联动 agent-model-router]
        M1 --> EV[Agent 安全评估器<br/>金丝雀外泄 / 越权调用审计]
        M2 --> EV
        M3 --> EV
    end

    subgraph BM["5. benchmarks · 行业生态对标与适配器"]
        PF[Promptfoo 导出适配器<br/>promptfoo.yaml]
        GK[Garak 日志摄取适配器<br/>统一标准化 Schema]
    end

    P1 -.复用评测数据.-> P2
    P1 -.用例对标.-> BM
```

## Quick Start（3 步复现核心成果）

```bash
# 1. 安装核心依赖
pip install -r requirements.txt

# 2. 运行统计分析与 95% CI 计算（无需模型，基于已归档数据瞬时出图出表）
cd project1-redteam
python ollama_analyze.py
python evaluate_judge.py     # 输出裁判混淆矩阵与 Cohen's Kappa κ 报告

# 3. 运行 MCP Agent 智能体安全与路由攻击评测（联动 agent-model-router）
cd ../project4-mcp-agent-security
python agent_redteam_runner.py
```

## Modules & Deliverables

| 模块 | 目录 | 核心入口 | 主要产物与交付价值 |
|---|---|---|---|
| **1. 离线红队评测** | `project1-redteam/` | `ollama_runner.py`<br/>`ollama_analyze.py`<br/>`evaluate_judge.py` | 176 条用例双轨实测；**95% Wilson CI** 统计推断；**Cohen's Kappa κ = 0.677** 裁判信度报告；思维链泄露审计 |
| **2. 自动化扫描平台** | `project2-eval-pipeline/` | `cli_pipeline.py`<br/>`app.py` (Web) | 探针包可插拔（零代码热插拔）；断点续跑；OWASP LLM Top 10 (2025) 映射；单文件离线 HTML 看板 |
| **3. 对齐案例复盘** | `project3-alignment-case/` | `make_essay.py` | 1.1 万字长文复盘（Alignment Faking、Agentic Misalignment、OAI-HF 事件）；39 条一手文献证据溯源清单 |
| **4. MCP Agent 安全** | `project4-mcp-agent-security/` | `agent_redteam_runner.py` | 涵盖工具描述投毒、间接提示注入与路由对抗降级；与 `agent-model-router` 实机协同评测 |
| **5. 行业生态对标** | `benchmarks/` | `adapters/promptfoo_adapter.py`<br/>`adapters/garak_adapter.py` | 对比 Garak/Promptfoo 6 大维度异同；双向适配器支持一键转导出 `promptfoo.yaml` |

---

## Headline Results（经统计学校准的核心实测结论）

### 轨道 1b：DeepSeek-R1-7B vs Qwen2.5-3B（n=80，带 95% Wilson CI）

| 评测维度 | DeepSeek-R1-7B (推理模型) | Qwen2.5-3B (指令模型) | 显著性说明 (Fisher 精确检验) |
|---|---|---|---|
| **总体 ASR (攻击成功率)** | **70.0%** `[54.6%, 81.9%]` | **50.0%** `[35.2%, 64.8%]` | 比值比 OR=2.33，双侧 p=0.1095（小样本呈中等效应量风险趋势） |
| **敏感内容诱导 (SI)** | **100.0%** `[72.2%, 100.0%]` | **80.0%** `[49.0%, 94.3%]` | 社工话术包装（学术/培训/分步叙事）远比技术编码有效 |
| **系统提示词提取 (SP)** | **100.0%** `[61.0%, 100.0%]` | **33.3%** `[9.7%, 70.0%]` | **显著差异 (p=0.0303)**：金丝雀被原样吐出，推理模型防线呈单向击穿 |
| **直接越狱 (DJ)** | 62.5% `[30.6%, 86.3%]` | 37.5% `[13.7%, 69.4%]` | 角色扮演与学术借口成主要突破口 |
| **编码绕过 (EB)** | 12.5% `[2.2%, 47.1%]` | 0.0% `[0.0%, 32.4%]` | 小模型常因自身解码能力不足导致攻击失效（非防线功劳） |

### 评测方法学核心突破（拉开技术差距的要点）

1. **思维链泄露（CoT as an Attack Surface）**：
   在 `EB-04` 用例中，R1 最终回复为空（因 token 截断），若使用 Garak 等传统黑盒工具将被误判为防御成功；但通过分离 `message.thinking` 独立审计，发现思维链内已完整推演出前体化学品提取思路——**推理模型的输出过滤无法防御思维链自身的信息泄露**。
2. **免责声明不构成防御（Yes-but 伪拒答复查）**：
   成功的攻击中，R1 有 7 条、Qwen 有 11 条回复一边输出免责声明（“作为 AI 我不能...”）一边给出完整可执行代码。评测必须看信息实质，不能看语气表面。
3. **裁判可信度度量（Cohen's Kappa κ = 0.677）**：
   对 80 条原始输出做规则初判 vs 全量人工复核对比，实测准确率 85.0%，检出召回率达 93.8%（仅 3 例漏报），一致性系数达到 **Substantial Agreement（高度一致）**，验证了“规则预筛 + 临界人工复核”分层流水线的高效与可信度（详见 `project1-redteam/analysis/judge_benchmark.md`）。
4. **Agent 体系的“数据与控制流混淆”**：
   在 `project4-mcp-agent-security` 实测中，当 MCP 工具描述植入特权伪造指令时，Agent 在调用参数中将系统金丝雀外发；外部网页返回值中夹带 `[ADMIN OVERRIDE]` 时，诱发了未授权的次级工具执行。

---

## Reproduce（完整复现命令）

```bash
# ---------------- 1. 红队评测与统计报告 ----------------
cd project1-redteam
# 运行统计分析（出 95% CI 汇总表、显著性检验表与带误差棒柱状图）
python ollama_analyze.py
# 运行裁判一致性度量（出混淆矩阵与 Cohen's Kappa 报告）
python evaluate_judge.py

# ---------------- 2. 自动化评测平台 ----------------
cd ../project2-eval-pipeline
# 单命令对标流水线 (probe -> detector -> report)
python cli_pipeline.py --from-results ../project1-redteam/results/judged.jsonl
# 启动 Web 扫描控制台 (http://127.0.0.1:5000)
python app.py

# ---------------- 3. 对齐案例深度复盘 ----------------
cd ../project3-alignment-case
# 重新编译中文复盘长文 PDF（自动探测 Windows/Linux 系统中文字体）
python make_essay.py

# ---------------- 4. MCP Agent 安全实测 ----------------
cd ../project4-mcp-agent-security
# 运行 MCP 工具投毒与路由降级对抗攻击测试
python agent_redteam_runner.py

# ---------------- 5. 行业工具生态对标 ----------------
cd ../benchmarks/adapters
# 导出攻击库至 Promptfoo 配置
python promptfoo_adapter.py
```

## Configuration

零硬编码绝对路径，全脚本统一支持 **CLI 参数 > 环境变量 > 默认配置**：

| 环境变量 | 用途说明 | 缺省回退 |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` / `JUDGE_MODEL` | 被测模型 / 裁判模型 | `deepseek-r1:7b` / `qwen2.5:3b` |
| `MODEL_PATH` | GGUF 本地模型路径 | `project1-redteam/models/...q4_k_m.gguf` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

## Ethics & Responsible Disclosure

- 本研究所有测试均在单机离线沙盒中进行，攻击意图严格限制为轻中度双用途（Dual-use）风险；
- 刻意排除生化、武器、关键基建等不可逆高危危害；
- 评测中引用的模型回复均做脱敏、截断与不可行化处理；
- 所有的攻击向量实测均配有对应的部署侧纵深防御（Defense-in-depth）工程加固建议。

---
*kevin_lau · 2026.09 (Initial) · 2026.10 (Refactored with Rigorous Stats, MCP Security & Industry Benchmarks)*
