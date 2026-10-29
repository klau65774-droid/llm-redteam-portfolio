#!/usr/bin/env bash
# restructure_repo.sh — 目录归并：消除冗余模块，保留三大顶层结构。
# 在仓库根目录执行：bash scripts/restructure_repo.sh
# 所有操作用 `git mv`，历史可追溯；`git rm -r --cached` 只清索引不清磁盘历史。
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "==> [1/2] 合并 project2-pipeline -> project2-eval-pipeline"
# 有效脚本：单文件 CLI 流水线（probe -> detector -> report）+ 其 HTML 模板。
# 目标目录已存在 Flask 版 scanner/ 包，CLI 版以独立文件名共存，避免命名冲突。
git mv project2-pipeline/pipeline.py            project2-eval-pipeline/cli_pipeline.py
git mv project2-pipeline/dashboard_template.html project2-eval-pipeline/dashboard_template.html
# 旧 README 的内容被 project2-eval-pipeline/README.md 完全覆盖，历史里可查，直接删除
git rm project2-pipeline/README.md
# 演示产物（可从 project1-redteam/results 重新生成），不入库
git rm -r --cached project2-pipeline/output >/dev/null 2>&1 || true
git rm -r project2-pipeline/output
git rm -r project2-pipeline

echo "==> [2/2] 合并 project3-alignment -> project3-alignment-case"
git mv project3-alignment/make_essay.py project3-alignment-case/make_essay.py
git mv "project3-alignment/对齐失败案例深度复盘.pdf" \
       "project3-alignment-case/对齐失败案例深度复盘.pdf"
git rm -r project3-alignment

echo "==> 完成。当前顶层结构："
ls -d project*/
