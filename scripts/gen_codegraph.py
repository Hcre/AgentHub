"""代码知识图谱生成器（双图谱：AI 可查 JSON + 人可视化 HTML）。

落地 conventions/08-code-understanding 规范在 AgentHub 规模（<5万行）的方案：
用 Python 标准库 ast 静态分析 src/backend/app，零外部依赖。

产出：
  .codegraph/graph.json          AI 侧：节点(MODULE/CLASS/FUNCTION) + 边(IMPORTS/CALLS/CONTAINS) + 缺陷检测
  .codegraph/graph_schema.json   节点/边定义（入 git）
  .understand-anything/graph.html 人侧：浏览器交互式可视化
  CODE_MAP.md                    人侧：Mermaid 全景图 + 关键入口表

用法: python scripts/gen_codegraph.py
"""

from __future__ import annotations

import ast
import json
import logging
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "backend" / "app"
PKG_PREFIX = "app"

# 5 层洋葱：模块路径 → 层 + 依赖序（数字越大越靠上层，禁止低层 → 高层）
LAYER_RULES = [
    ("app.api", "L4-api", 4),
    ("app.application", "L3-application", 3),
    ("app.domain", "L2-domain", 2),
    ("app.infrastructure", "L1-infrastructure", 1),
    ("app.core", "L0-core", 0),
    ("app.schemas", "LX-schemas", 0),
]


def layer_of(module: str) -> tuple[str, int]:
    for prefix, name, order in LAYER_RULES:
        if module == prefix or module.startswith(prefix + "."):
            return name, order
    return "other", 0


def module_name(py_file: Path) -> str:
    """src/backend/app/application/services/chat_service.py → app.application.services.chat_service"""
    rel = py_file.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_py_files():
    for f in sorted(SRC.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        yield f


def build_graph() -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    # 收集所有已定义函数/类全名，用于把 CALLS 解析到内部节点
    defined_funcs: dict[str, str] = {}  # 简单名 → 节点 id（取首个，够本规模用）

    files = list(iter_py_files())

    # Pass 1：建模块/类/函数节点 + CONTAINS
    for f in files:
        mod = module_name(f)
        layer, order = layer_of(mod)
        nodes[mod] = {"id": mod, "type": "MODULE", "layer": layer, "order": order,
                      "is_package": f.name == "__init__.py",
                      "file": str(f.relative_to(ROOT)).replace("\\", "/")}
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as exc:
            logger.warning("跳过解析失败: %s (%s)", f, exc)
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fid = f"{mod}.{node.name}"
                nodes[fid] = {"id": fid, "type": "FUNCTION", "layer": layer, "order": order, "module": mod}
                edges.append({"src": mod, "dst": fid, "rel": "CONTAINS"})
                defined_funcs.setdefault(node.name, fid)
            elif isinstance(node, ast.ClassDef):
                cid = f"{mod}.{node.name}"
                nodes[cid] = {"id": cid, "type": "CLASS", "layer": layer, "order": order, "module": mod}
                edges.append({"src": mod, "dst": cid, "rel": "CONTAINS"})
                for b in node.body:
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mid = f"{cid}.{b.name}"
                        nodes[mid] = {"id": mid, "type": "FUNCTION", "layer": layer, "order": order, "module": mod}
                        edges.append({"src": cid, "dst": mid, "rel": "CONTAINS"})
                        defined_funcs.setdefault(b.name, mid)

    # Pass 2：IMPORTS（模块级，精确）
    # 注：不抽 CALLS——Python 无类型推断时按裸函数名解析调用会产生大量假边
    #     （同名方法误归因），污染图谱与缺陷检测。依赖关系以 IMPORTS 为准，
    #     这也正是 import-linter / AR-01 的判据。
    seen_imports: set[tuple[str, str]] = set()
    for f in files:
        mod = module_name(f)
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PKG_PREFIX):
                target = node.module
                # 归一到已知模块节点（target 可能是包，落到最近的已知模块）
                t = target
                while t and t not in nodes:
                    t = t.rsplit(".", 1)[0] if "." in t else ""
                if t and t != mod and (mod, t) not in seen_imports:
                    seen_imports.add((mod, t))
                    edges.append({"src": mod, "dst": t, "rel": "IMPORTS"})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(PKG_PREFIX):
                        t = alias.name
                        while t and t not in nodes:
                            t = t.rsplit(".", 1)[0] if "." in t else ""
                        if t and t != mod and (mod, t) not in seen_imports:
                            seen_imports.add((mod, t))
                            edges.append({"src": mod, "dst": t, "rel": "IMPORTS"})

    defects = detect_defects(nodes, edges)
    return {"nodes": list(nodes.values()), "edges": edges, "defects": defects,
            "stats": {"modules": sum(1 for n in nodes.values() if n["type"] == "MODULE"),
                      "classes": sum(1 for n in nodes.values() if n["type"] == "CLASS"),
                      "functions": sum(1 for n in nodes.values() if n["type"] == "FUNCTION"),
                      "edges": len(edges)}}


def detect_defects(nodes: dict, edges: list) -> dict:
    """缺陷检测：跨层违规（AR-01）+ 循环依赖 + 模块级死代码。"""
    mod_imports = defaultdict(set)
    for e in edges:
        if e["rel"] == "IMPORTS" and e["src"] in nodes and e["dst"] in nodes:
            mod_imports[e["src"]].add(e["dst"])

    # 跨层违规：低 order 模块依赖高 order 模块（违反 L5→L4→L3→L2←L1 单向）
    # 例外：infrastructure(L1) 实现 domain(L2) 接口属依赖倒置，允许 L1→L2
    layer_violations = []
    for src, dsts in mod_imports.items():
        so = nodes[src]["order"]
        for dst in dsts:
            do = nodes[dst]["order"]
            if so and do and so < do:  # 低层依赖高层
                if not (nodes[src]["layer"].startswith("L1") and nodes[dst]["layer"].startswith("L2")):
                    layer_violations.append({"src": src, "dst": dst,
                                             "from": nodes[src]["layer"], "to": nodes[dst]["layer"]})

    # 循环依赖（模块级，DFS 找环）
    cycles = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = defaultdict(int)
    stack: list[str] = []

    def dfs(u: str):
        color[u] = GRAY
        stack.append(u)
        for v in mod_imports.get(u, ()):
            if color[v] == GRAY:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
            elif color[v] == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for m in [n["id"] for n in nodes.values() if n["type"] == "MODULE"]:
        if color[m] == WHITE:
            dfs(m)

    # 死代码（无入边的非入口模块；main/__init__/api 路由排除）
    has_incoming = set()
    for e in edges:
        if e["rel"] == "IMPORTS":
            has_incoming.add(e["dst"])
    # 排除：包命名空间(__init__，聚合器，不按名 import)、入口(main)、API 路由(被框架反射注册)
    dead = [n["id"] for n in nodes.values()
            if n["type"] == "MODULE" and n["id"] not in has_incoming
            and not n.get("is_package") and not n["id"].endswith(".main")
            and ".api." not in n["id"] + "." and n["id"] != "app"]

    return {"layer_violations": layer_violations, "cycles": cycles, "dead_modules": dead}


SCHEMA = {
    "node_types": ["MODULE", "CLASS", "FUNCTION"],
    "edge_types": ["CONTAINS", "IMPORTS"],
    "layers": [r[1] for r in LAYER_RULES],
    "dependency_rule": "L5→L4→L3→L2←L1（低层禁依赖高层；L1→L2 依赖倒置例外）",
    "note": "依赖关系以 IMPORTS（静态精确）为准；不抽 CALLS（Python 无类型推断时按名解析会产生假边）",
}


def main() -> int:
    if not SRC.is_dir():
        logger.error("源目录不存在: %s", SRC)
        return 1
    logger.info("扫描 %s ...", SRC.relative_to(ROOT))
    graph = build_graph()

    cg = ROOT / ".codegraph"
    cg.mkdir(exist_ok=True)
    (cg / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (cg / "graph_schema.json").write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")

    ua = ROOT / ".understand-anything"
    ua.mkdir(exist_ok=True)
    (ua / "graph.html").write_text(render_html(graph), encoding="utf-8")

    (ROOT / "CODE_MAP.md").write_text(render_code_map(graph), encoding="utf-8")

    s = graph["stats"]
    d = graph["defects"]
    logger.info("✅ 节点 %d 模块 / %d 类 / %d 函数 · 边 %d",
                s["modules"], s["classes"], s["functions"], s["edges"])
    logger.info("🔍 跨层违规 %d · 循环依赖 %d · 死代码模块 %d",
                len(d["layer_violations"]), len(d["cycles"]), len(d["dead_modules"]))
    logger.info("产出: .codegraph/graph.json · .understand-anything/graph.html · CODE_MAP.md")
    return 0


def render_code_map(graph: dict) -> str:
    """人读：Mermaid 模块层级图 + 关键入口表。"""
    mods = [n for n in graph["nodes"] if n["type"] == "MODULE"]
    by_layer = defaultdict(list)
    for n in mods:
        by_layer[n["layer"]].append(n["id"])

    lines = ["# CODE_MAP — AgentHub 后端代码地图",
             "",
             "> 由 `python scripts/gen_codegraph.py` 自动生成，请勿手改。",
             f"> 规模：{graph['stats']['modules']} 模块 / {graph['stats']['classes']} 类 / "
             f"{graph['stats']['functions']} 函数 / {graph['stats']['edges']} 边。",
             "",
             "## 一、5 层洋葱模块全景（Mermaid）",
             "",
             "> 边 = 模块间 IMPORTS（静态精确）。依赖方向应为 L5→L4→L3→L2←L1。",
             "",
             "```mermaid",
             "graph TD"]

    # 模块级边（聚合到子包，避免太密）
    def pkg(m: str) -> str:
        parts = m.split(".")
        return ".".join(parts[:3]) if len(parts) >= 3 else m

    pkg_edges = set()
    for e in graph["edges"]:
        if e["rel"] == "IMPORTS":
            a, b = pkg(e["src"]), pkg(e["dst"])
            if a != b:
                pkg_edges.add((a, b))
    for a, b in sorted(pkg_edges):
        sa = a.replace(".", "_")
        sb = b.replace(".", "_")
        lines.append(f"    {sa}[{a}] --> {sb}[{b}]")
    lines.append("```")
    lines.append("")

    lines.append("## 二、按层模块清单")
    lines.append("")
    for layer in ["L4-api", "L3-application", "L2-domain", "L1-infrastructure", "L0-core", "LX-schemas", "other"]:
        if layer not in by_layer:
            continue
        lines.append(f"### {layer}")
        for m in sorted(by_layer[layer]):
            lines.append(f"- `{m}`")
        lines.append("")

    # 关键入口：api 层模块
    lines.append("## 三、关键入口（API 层）")
    lines.append("")
    api_mods = sorted(m["id"] for m in mods if ".api." in m["id"] + "." or m["id"].endswith(".main"))
    for m in api_mods:
        lines.append(f"- `{m}`")
    lines.append("")

    # 缺陷
    d = graph["defects"]
    lines.append("## 四、自动缺陷检测")
    lines.append("")
    lines.append(f"- 跨层违规（AR-01）：**{len(d['layer_violations'])}**")
    for v in d["layer_violations"][:20]:
        lines.append(f"  - 🔴 `{v['src']}` ({v['from']}) → `{v['dst']}` ({v['to']})")
    lines.append(f"- 循环依赖：**{len(d['cycles'])}**")
    for c in d["cycles"][:20]:
        lines.append(f"  - 🔴 {' → '.join(c)}")
    lines.append(f"- 无入边模块（疑似死代码，需人工确认）：**{len(d['dead_modules'])}**")
    for m in d["dead_modules"][:30]:
        lines.append(f"  - 🟡 `{m}`")
    lines.append("")
    return "\n".join(lines)


def render_html(graph: dict) -> str:
    """人看：浏览器交互式力导向图（内联，零依赖，CDN 加载 d3）。"""
    mods = [n for n in graph["nodes"] if n["type"] == "MODULE"]
    layer_color = {"L4-api": "#6366f1", "L3-application": "#0ea5e9", "L2-domain": "#10b981",
                   "L1-infrastructure": "#f59e0b", "L0-core": "#94a3b8", "LX-schemas": "#a78bfa", "other": "#cbd5e1"}
    d3nodes = [{"id": m["id"], "layer": m["layer"], "color": layer_color.get(m["layer"], "#ccc")} for m in mods]
    modset = {m["id"] for m in mods}
    d3links = [{"source": e["src"], "target": e["dst"], "rel": e["rel"]}
               for e in graph["edges"] if e["rel"] == "IMPORTS"
               and e["src"] in modset and e["dst"] in modset]
    data = json.dumps({"nodes": d3nodes, "links": d3links}, ensure_ascii=False)
    defects = json.dumps(graph["defects"], ensure_ascii=False)
    return _HTML_TEMPLATE.replace("__DATA__", data).replace("__DEFECTS__", defects)


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>AgentHub 代码图谱（人视图）</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
  body{margin:0;font:14px system-ui;background:#0f172a;color:#e2e8f0}
  #bar{padding:10px 16px;background:#1e293b;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
  .legend{display:flex;gap:6px;align-items:center}
  .dot{width:12px;height:12px;border-radius:50%}
  svg{width:100vw;height:calc(100vh - 90px)}
  .node text{font-size:10px;fill:#e2e8f0;pointer-events:none}
  .link{stroke:#475569;stroke-opacity:.5}
  .link.CALLS{stroke:#f87171;stroke-dasharray:3 2}
  #info{padding:6px 16px;background:#1e293b;font-size:12px;color:#94a3b8}
  .hl{stroke:#fde047;stroke-width:2.5px}
</style></head><body>
<div id="bar"><b>AgentHub 代码图谱</b><span style="color:#94a3b8">点节点高亮其依赖 · 拖动布局 · 滚轮缩放</span>
<span class="legend"><span class="dot" style="background:#6366f1"></span>L4-api</span>
<span class="legend"><span class="dot" style="background:#0ea5e9"></span>L3-app</span>
<span class="legend"><span class="dot" style="background:#10b981"></span>L2-domain</span>
<span class="legend"><span class="dot" style="background:#f59e0b"></span>L1-infra</span>
<span style="color:#94a3b8">边=IMPORTS</span>
</div>
<div id="info">就绪</div>
<svg></svg>
<script>
const G=__DATA__, DEF=__DEFECTS__;
const svg=d3.select("svg"), W=window.innerWidth, H=window.innerHeight-90;
const g=svg.append("g");
svg.call(d3.zoom().on("zoom",e=>g.attr("transform",e.transform)));
const sim=d3.forceSimulation(G.nodes)
  .force("link",d3.forceLink(G.links).id(d=>d.id).distance(60))
  .force("charge",d3.forceManyBody().strength(-180))
  .force("center",d3.forceCenter(W/2,H/2));
const link=g.append("g").selectAll("line").data(G.links).join("line")
  .attr("class",d=>"link "+d.rel);
const node=g.append("g").selectAll("g").data(G.nodes).join("g").attr("class","node")
  .call(d3.drag().on("start",ds).on("drag",dd).on("end",de));
node.append("circle").attr("r",6).attr("fill",d=>d.color).attr("stroke","#0f172a");
node.append("text").attr("x",8).attr("dy",3).text(d=>d.id.replace("app.",""));
const adj={}; G.links.forEach(l=>{(adj[l.source.id||l.source]=adj[l.source.id||l.source]||new Set()).add(l.target.id||l.target);});
node.on("click",(e,d)=>{
  const keep=new Set([d.id]); (adj[d.id]||[]).forEach(x=>keep.add(x));
  node.select("circle").classed("hl",n=>n.id===d.id);
  node.style("opacity",n=>keep.has(n.id)?1:.15);
  link.style("opacity",l=>((l.source.id===d.id)||(l.target.id===d.id))?.9:.04);
  const outs=[...(adj[d.id]||[])].map(x=>x.replace("app.","")).join(", ")||"（无）";
  document.getElementById("info").innerHTML=`<b>${d.id}</b> ｜ ${d.layer} ｜ 依赖→ ${outs}`;
});
svg.on("dblclick.zoom",null);
svg.on("click",e=>{if(e.target.tagName==="svg"){node.style("opacity",1);link.style("opacity",null);node.select("circle").classed("hl",false);document.getElementById("info").textContent="就绪";}});
sim.on("tick",()=>{
  link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("transform",d=>`translate(${d.x},${d.y})`);
});
function ds(e,d){if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;}
function dd(e,d){d.fx=e.x;d.fy=e.y;}
function de(e,d){if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
const nv=DEF.layer_violations.length, nc=DEF.cycles.length, nd=DEF.dead_modules.length;
document.getElementById("info").textContent=`就绪 · 跨层违规 ${nv} · 循环依赖 ${nc} · 无入边模块 ${nd}（点节点查依赖）`;
</script></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
