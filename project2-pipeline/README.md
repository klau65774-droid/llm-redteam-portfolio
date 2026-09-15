# 自动化红队评测流水线（项目 2）

单命令完成「加载模型 → 执行测试集 → 判定 → 渲染可视化 HTML 报告」。
对标 garak / inspect_ai 的核心链路（probe → detector → report），
零框架依赖（仅推理阶段需要 llama-cpp-python），报告为单文件 HTML，离线可开。

## 用法

```bash
# 完整评测一个新模型（GGUF）
python pipeline.py --model ../project1-redteam/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --testset ../project1-redteam/prompts/test_set.json

# 用已有判定结果直接渲染报告（演示/复用）
python pipeline.py --from-results ../project1-redteam/results/judged.jsonl
```

输出：`output/dashboard.html` —— KPI 总览、分类别/分模板成功率条形图、
96 条记录可筛选可展开的明细表。

## 与项目 1 的关系

项目 1 回答"这个模型安不安全"（一次性研究）；
项目 2 回答"如何让任何模型都能被快速评测"（工程化）。
测试集、判定口径沿用项目 1，新增：CLI 流水线封装、自动判定器接口
（可替换为 LLM-as-judge）、单文件交互式报告渲染器。

## 文件

- `pipeline.py` —— 流水线主程序（推理 / 判定 / 渲染三阶段）
- `dashboard_template.html` —— 报告模板（数据占位符 `__DATA__`）
- `output/dashboard.html` —— 基于项目 1 结果生成的成品报告
