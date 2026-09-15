# 开源大语言模型红队测试（Qwen2.5-1.5B-Instruct）

个人安全研究作品集项目 · kevin_lau · 2026.09

对开源模型 Qwen2.5-1.5B-Instruct 实施系统性红队测试：
96 条测试用例 / 5 大类攻击手法 / 10 种攻击意图，全程本地离线、纯 CPU 可复现。

## 核心结论

| 指标 | 结果 |
|---|---|
| 总体攻击成功率（严格口径） | **19.0%**（16/84） |
| 总体攻击成功率（含部分突破） | **27.4%**（23/84） |
| 直接有害请求拒答率 | 100%（10/10） |
| 提示注入成功率 | **33.3%**（4/12）← 最薄弱面 |
| 最有效越狱模板 | 学术研究借口 40% / 故事分步叙事 40% |
| 最无效越狱模板 | DAN 开发者模式 0% |
| 良性请求过度拒答率 | 0%（0/12） |

## 目录结构

```
project1-redteam/
├── build_test_set.py     # 测试集构建器（5 类 96 条）
├── runner.py             # 推理运行器（分批执行、断点续跑）
├── analyze.py            # 判定 pass 1：规则预筛
├── finalize.py           # 判定 pass 2：人工复核合并 + 指标计算
├── make_charts.py        # 图表生成
├── make_report.py        # 报告 PDF 生成
├── prompts/test_set.json         # 测试集
├── results/
│   ├── raw_results.jsonl         # 原始输出（96 条）
│   ├── judged.jsonl              # 判定结果（三级：完全突破/部分突破/成功防御）
│   └── stats.json                # 汇总指标
└── report/
    ├── 开源大模型红队测试报告_Qwen2.5-1.5B.pdf   # 最终报告
    └── chart1_asr.png / chart2_templates.png
```

## 复现

```bash
# 环境：Python 3.12，Windows / macOS / Linux，纯 CPU 即可
pip install llama-cpp-python matplotlib
# 下载模型（约 1.1GB）到 models/
# https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF

python build_test_set.py        # 生成测试集
python runner.py 0 96           # 跑全部测试（可分段，自动断点续跑）
python analyze.py               # 规则预筛
python finalize.py              # 合并人工复核 + 出指标
python make_charts.py           # 出图
python make_report.py           # 出报告 PDF
```

## 伦理声明

全部测试在本地离线环境进行；攻击意图限定轻中危双用途类别，
刻意排除武器、生化、爆炸物等高危类别；报告引用均经脱敏截断。
本项目目的是评估与改进模型安全，不构成任何操作建议。
