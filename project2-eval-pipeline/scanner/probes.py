# -*- coding: utf-8 -*-
"""探针包加载：probes/*.json 即插即用。

探针包格式（兼容并扩展自项目1 attacks.json）：
{
  "meta": {
    "name": "redteam_basic",            # 包名 = 文件名（不带 .json）
    "title": "展示用标题",
    "source": "出处说明",
    "category_owasp_map": {"<category>": "LLM01", ...},  # 类别 → OWASP 编号
    "owasp_names": {"LLM01": "Prompt Injection", ...}     # 编号 → 名称（可选）
  },
  "cases": [
    {"id", "category", "technique", "system?", "prompt",
     "goal", "success_any", "success_all"}
  ]
}

扩展点：未来适配 garak probe 时，只需编写一个适配器把 garak probe
产出的 prompts 转成上述 cases 结构即可，引擎与判定层无需改动。
"""
import json
import os

# probes 目录默认在包同级（项目根/probes/）
DEFAULT_PROBES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes"
)

REQUIRED_CASE_FIELDS = ("id", "category", "prompt")


class ProbePackError(Exception):
    """探针包格式错误。"""


def list_packs(probes_dir: str = DEFAULT_PROBES_DIR) -> list:
    """列出 probes_dir 下全部探针包的摘要信息。"""
    packs = []
    if not os.path.isdir(probes_dir):
        return packs
    for fname in sorted(os.listdir(probes_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(probes_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {})
            packs.append({
                "name": meta.get("name") or fname[:-5],
                "title": meta.get("title", fname),
                "description": meta.get("description", ""),
                "source": meta.get("source", ""),
                "n_cases": len(data.get("cases", [])),
                "file": fname,
            })
        except (json.JSONDecodeError, OSError) as e:
            packs.append({"name": fname[:-5], "title": fname,
                          "error": str(e), "n_cases": 0, "file": fname})
    return packs


def load_pack(name: str, probes_dir: str = DEFAULT_PROBES_DIR) -> dict:
    """按包名加载并校验一个探针包，返回 {meta, cases}，cases 已补上 owasp 字段。"""
    path = os.path.join(probes_dir, name + ".json")
    if not os.path.isfile(path):
        raise ProbePackError(f"探针包不存在: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    meta = data.setdefault("meta", {})
    meta.setdefault("name", name)
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ProbePackError(f"探针包 {name} 缺少 cases")
    owasp_map = meta.get("category_owasp_map", {})
    seen_ids = set()
    for c in cases:
        for field in REQUIRED_CASE_FIELDS:
            if field not in c:
                raise ProbePackError(f"用例缺少必填字段 {field}: {c}")
        if c["id"] in seen_ids:
            raise ProbePackError(f"用例 id 重复: {c['id']}")
        seen_ids.add(c["id"])
        c.setdefault("success_any", [])
        c.setdefault("success_all", [])
        c.setdefault("technique", "")
        c.setdefault("goal", "")
        # 每条用例挂上 OWASP 映射（类别级，可被用例级 owasp 字段覆盖）
        c["owasp"] = c.get("owasp") or owasp_map.get(c["category"], "未映射")
    return data


def collect_cases(pack_names: list, probes_dir: str = DEFAULT_PROBES_DIR) -> tuple:
    """加载多个探针包并合并用例；返回 (cases, packs_meta)。用例附加 pack 字段。"""
    all_cases, metas = [], []
    for name in pack_names:
        pack = load_pack(name, probes_dir)
        metas.append(pack["meta"])
        for c in pack["cases"]:
            c = dict(c)
            c["pack"] = pack["meta"]["name"]
            all_cases.append(c)
    return all_cases, metas
