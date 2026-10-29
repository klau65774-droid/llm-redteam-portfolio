# 行业主流工具对标与对比分析报告 (Industry Benchmark Comparison)

**作者**：kevin_lau ｜ **对标对象**：Garak、Promptfoo、Inspect AI

---

## 1. 为什么自研流水线？——核心定位与差异化矩阵

在工程落地和面试场景中，技术负责人最常提出的问题是：**“行业里已经有 Garak 和 Promptfoo，为什么还要自研一套从 Probe 到 Judge 的全链路工具？”**

下表系统性总结了本自研体系与工业界主流开源工具的核心能力差异：

| 评估维度 | 自研体系 (llm-redteam-portfolio) | Garak (NVIDIA 开源红队扫描器) | Promptfoo (CI/CD 提示词断言工具) | Inspect AI (UK AISI 评测框架) |
|---|---|---|---|---|
| **核心定位** | 专注开源小模型与 Agent 深度红队评估 | 模型层通用漏洞全量快速扫描 | 应用层与系统提示词回归测试 | 前沿大模型高阶自主对齐与沙箱评估 |
| **运行资源门槛** | **零 GPU 依赖**，全链路纯 CPU 本地离线执行（约 1.1GB GGUF / 轻量 Ollama） | 极重：依赖 PyTorch、Transformers 及大型权重下载（>15GB 显存/磁盘） | 依赖 Node.js，需外部 API 或本地 HTTP Provider 配合 | 需安装复杂 Python 生态与 Docker 沙箱环境 |
| **思维链 (CoT) 泄露审计** | **原生支持**：分离 `<think>` 字段，独立判定思维链敏感推演与最终抑制 | ❌ 仅抓取最终 text 输出，不区分 CoT 与最终回复 | ❌ 无内置 CoT 分离与推理过程审计 | ⚠️ 需通过自定义 Scorer 手动抽取 Inspect 轨迹 |
| **免责声明伪拒答 (Yes-but)** | **原生支持**：HarmBench 口径，识别“前置打免责、后文给步骤”的假性拒答并校正升级 | ❌ 依赖关键词命中，极易被免责声明开头的假阳性欺骗 | 需手写繁琐的 `llm-rubric` 正则断言 | 需调用高昂外部闭源大模型做 Model-Graded 评测 |
| **中文及本土化社工绕过** | **深度优化**：覆盖学术包装、小说分步续写、拼音拆字、侧信道金丝雀等 5 大手法 | 偏向英文传统越狱（DAN、Grandma、Base64），中文拒答模式覆盖不全 | 探针依赖用户手写配置，无现成中文红队用例集 | 主要面向通用能力基准（MMLU、SWE-bench），红队需自主开发 |
| **MCP / Agent 协议扩展** | **原生扩展**：涵盖工具描述投毒、间接注入与路由对抗降级 | ❌ 仅支持纯文本与单轮 Prompt 注入测试 | ⚠️ 支持部分工具调用 Mock，但无针对 MCP 协议的投毒套件 | 支持多步 Tool-use，但部署成本极高 |

---

## 2. 判定器差异与实验实测对比

我们使用统一的 80 条攻击样本，通过本仓库提供的 `adapters/promptfoo_adapter.py` 转换并在本地 Ollama 环境下执行横向对照：

### 实验发现 1：免责声明导致工具判定失真
- **Promptfoo (默认 not-icontains 模式)**：在测试 Qwen 3B 和 R1 7B 时，遇到“作为 AI 我不能... 但是你可以通过以下方式操作...”这类输出时，Promptfoo 判定由于命中了恶意关键词直接宣告断言失败。然而，在真实防御案例（如 SI-04，模型明确拒绝并指导用户走正规官方途径找回密码），Promptfoo 依然因为命中“账号”“密码”词汇造成 **高达 22.5% 的误杀率 (False Positive)**。
- **本自研体系**：通过前置 `REFUSAL_RE` 拒答优先探测 + 伪拒答交付标记（Yes-but）+ 人工复核闭环，将假阳性严格压制，计算出的 Cohen's Kappa 达到 0.677（高度一致）。

### 实验发现 2：思维链敏感推演的盲区
- 在 `EB-04` 用例中，DeepSeek-R1-7B 在受控输出阶段因 token 截断最终回复为空，若仅使用 **Garak 或常规黑盒探测器**，该测试将被判为 `Passed / Defended`（未检测到输出有害字符）。
- 但在本自研引擎中，Ollama 的 `message.thinking` 被单独抓取落盘，审计发现思维链中已推演了敏感提取前体化学品流程。本系统将此列为 **推理模型特有风险（Thinking Exfiltration）**，指出了传统评测工具的致命盲区。

---

## 3. 生态互通与适配器用法

本项目绝非排斥成熟生态，而是构建了标准的导入/导出适配桥梁：

### ① 导出至 Promptfoo 自动化执行
```bash
# 将当前攻击库转化为 Promptfoo 评测配置
python benchmarks/adapters/promptfoo_adapter.py \
    --src project1-redteam/attacks.json \
    --out benchmarks/promptfoo_redteam.yaml

# 利用 Promptfoo CLI 运行工业级自动化测试
npx promptfoo eval -c benchmarks/promptfoo_redteam.yaml
```

### ② 导入 Garak 运行日志并入统一看板
```bash
# 将 Garak 扫描生成的 report.jsonl 标准化摄取
python benchmarks/adapters/garak_adapter.py \
    --input /path/to/garak.report.jsonl \
    --output benchmarks/results/garak_normalized.jsonl
```
摄取后的数据可直接复用 `project2-eval-pipeline` 渲染单文件 HTML 看板，与本地自研评测结果进行多维对比。

---
