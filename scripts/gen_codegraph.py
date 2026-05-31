"""代码知识图谱生成器（双图谱：AI 可查 JSON + 人可视化 HTML）。

落地 conventions/08-code-understanding 规范在 AgentHub 规模（<5万行）的方案：
用 Python 标准库 ast 静态分析 src/backend/app，零外部依赖。

产出：
  .codegraph/graph.json          AI 侧：节点(MODULE/CLASS/FUNCTION) + 边(IMPORTS/CALLS/CONTAINS) + 缺陷检测
  .codegraph/graph_schema.json   节点/边定义（入 git）
  .understand-anything/graph.html 人侧：浏览器交互式可视化
  docs/CODE-MAP_代码地图.md               人侧：Mermaid 全景图 + 关键入口表

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

    (ROOT / "docs" / "CODE-MAP_代码地图.md").write_text(render_code_map(graph), encoding="utf-8")

    s = graph["stats"]
    d = graph["defects"]
    logger.info("✅ 节点 %d 模块 / %d 类 / %d 函数 · 边 %d",
                s["modules"], s["classes"], s["functions"], s["edges"])
    logger.info("🔍 跨层违规 %d · 循环依赖 %d · 死代码模块 %d",
                len(d["layer_violations"]), len(d["cycles"]), len(d["dead_modules"]))
    logger.info("产出: .codegraph/graph.json · .understand-anything/graph.html · docs/CODE-MAP_代码地图.md")
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
    """人看：浏览器交互式分层图。零外部依赖（纯原生 SVG/JS，无 CDN），离线可开。

    按 5 层洋葱横向分带布局，点节点高亮上下游（依赖/被依赖），可缩放平移。
    """
    mods = [n for n in graph["nodes"] if n["type"] == "MODULE" and not n.get("is_package")]
    modset = {m["id"] for m in mods}
    links = [{"s": e["src"], "t": e["dst"]}
             for e in graph["edges"] if e["rel"] == "IMPORTS"
             and e["src"] in modset and e["dst"] in modset]
    payload = {
        "nodes": [{"id": m["id"], "layer": m["layer"]} for m in mods],
        "links": links,
        "defects": graph["defects"],
        "stats": graph["stats"],
    }
    return _HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>AgentHub 代码图谱（人视图）</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;font:13px system-ui,"Microsoft YaHei";background:#0f172a;color:#e2e8f0;overflow:hidden}
  #bar{padding:8px 14px;background:#1e293b;display:flex;gap:14px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #334155}
  #bar b{font-size:15px}
  .legend{display:flex;gap:5px;align-items:center;font-size:12px}
  .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
  #wrap{display:flex;height:calc(100vh - 88px)}
  svg{flex:1;background:#0f172a;cursor:grab}
  svg:active{cursor:grabbing}
  #side{width:300px;background:#1e293b;border-left:1px solid #334155;padding:12px 14px;overflow:auto;font-size:12px}
  #side h3{margin:0 0 6px;font-size:13px;color:#cbd5e1}
  #side .mut{color:#94a3b8}
  #side code{background:#0f172a;padding:1px 5px;border-radius:4px;color:#93c5fd;font-size:11px}
  .lbl{font-size:9px;fill:#cbd5e1;pointer-events:none}
  .edge{stroke:#3b4960;stroke-width:1;fill:none}
  .edge.up{stroke:#fbbf24;stroke-width:1.6}
  .edge.down{stroke:#38bdf8;stroke-width:1.6}
  circle.nd{stroke:#0f172a;stroke-width:1.2;cursor:pointer}
  circle.nd.sel{stroke:#fde047;stroke-width:3}
  circle.nd.bad{stroke:#f87171;stroke-width:3}
  .band{fill:#1e293b;opacity:.35}
  .bandlbl{fill:#64748b;font-size:11px;font-weight:bold}
  #status{padding:5px 14px;background:#1e293b;border-top:1px solid #334155;font-size:12px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style></head><body>
<div id="bar"><b>AgentHub 代码图谱</b>
<span class="legend"><span class="dot" style="background:#6366f1"></span>L4-api</span>
<span class="legend"><span class="dot" style="background:#0ea5e9"></span>L3-app</span>
<span class="legend"><span class="dot" style="background:#10b981"></span>L2-domain</span>
<span class="legend"><span class="dot" style="background:#f59e0b"></span>L1-infra</span>
<span class="legend"><span class="dot" style="background:#94a3b8"></span>L0-core</span>
<span class="legend"><span class="dot" style="background:#a78bfa"></span>schemas</span>
<span class="mut" style="color:#94a3b8">｜ <span style="color:#fbbf24">━</span> 上游(被它依赖) <span style="color:#38bdf8">━</span> 下游(它依赖) ｜ 点节点查看 · 滚轮缩放 · 拖空白平移</span>
</div>
<div id="wrap">
  <svg id="svg"></svg>
  <div id="side"><h3>使用</h3><p class="mut">点任意节点：高亮它的<b style="color:#fbbf24">上游</b>（谁 import 它，改它会波及）和<b style="color:#38bdf8">下游</b>（它 import 谁）。点空白处复位。</p><div id="detail"></div></div>
</div>
<div id="status"></div>
<script>
const P=__PAYLOAD__;
const LC={"L4-api":"#6366f1","L3-application":"#0ea5e9","L2-domain":"#10b981","L1-infrastructure":"#f59e0b","L0-core":"#94a3b8","LX-schemas":"#a78bfa","other":"#cbd5e1"};
const ORDER=["L4-api","L3-application","L2-domain","L1-infrastructure","L0-core","LX-schemas","other"];
const svg=document.getElementById("svg");
const NS="http://www.w3.org/2000/svg";
const Wd=svg.clientWidth||window.innerWidth-300, Ht=svg.clientHeight||window.innerHeight-88;

// 分层布局：每层一条横带，带内按 id 排开
const byLayer={}; ORDER.forEach(l=>byLayer[l]=[]);
P.nodes.forEach(n=>{(byLayer[n.layer]=byLayer[n.layer]||[]).push(n);});
const usedLayers=ORDER.filter(l=>byLayer[l]&&byLayer[l].length);
const bandH=Math.max(70,(Ht-40)/usedLayers.length);
const pos={};
usedLayers.forEach((l,li)=>{
  const arr=byLayer[l].sort((a,b)=>a.id.localeCompare(b.id));
  const y=30+li*bandH+bandH/2;
  arr.forEach((n,i)=>{pos[n.id]={x:70+(i+0.5)*((Wd-120)/arr.length),y:y+((i%2)?14:-14)};});
});

// 邻接
const out={},inc={};
P.nodes.forEach(n=>{out[n.id]=new Set();inc[n.id]=new Set();});
P.links.forEach(l=>{if(out[l.s]){out[l.s].add(l.t);inc[l.t].add(l.s);}});

const root=document.createElementNS(NS,"g");svg.appendChild(root);
// 层带 + 标签
usedLayers.forEach((l,li)=>{
  const y=30+li*bandH;
  const r=document.createElementNS(NS,"rect");
  r.setAttribute("class","band");r.setAttribute("x",0);r.setAttribute("y",y);
  r.setAttribute("width",Wd);r.setAttribute("height",bandH-6);root.appendChild(r);
  const t=document.createElementNS(NS,"text");t.setAttribute("class","bandlbl");
  t.setAttribute("x",8);t.setAttribute("y",y+16);t.textContent=l;root.appendChild(t);
});
// 边
const elayer=document.createElementNS(NS,"g");root.appendChild(elayer);
const edgeEls=P.links.map(l=>{
  const p=document.createElementNS(NS,"line");p.setAttribute("class","edge");
  const a=pos[l.s],b=pos[l.t];if(!a||!b)return null;
  p.setAttribute("x1",a.x);p.setAttribute("y1",a.y);p.setAttribute("x2",b.x);p.setAttribute("y2",b.y);
  p.__s=l.s;p.__t=l.t;elayer.appendChild(p);return p;
}).filter(Boolean);
// 节点
const nlayer=document.createElementNS(NS,"g");root.appendChild(nlayer);
const dead=new Set(P.defects.dead_modules||[]);
const circles={};
P.nodes.forEach(n=>{
  const p=pos[n.id];if(!p)return;
  const c=document.createElementNS(NS,"circle");
  c.setAttribute("class","nd"+(dead.has(n.id)?" bad":""));
  c.setAttribute("cx",p.x);c.setAttribute("cy",p.y);c.setAttribute("r",5);
  c.setAttribute("fill",LC[n.layer]||"#ccc");
  c.addEventListener("click",ev=>{ev.stopPropagation();select(n.id);});
  nlayer.appendChild(c);circles[n.id]=c;
  const t=document.createElementNS(NS,"text");t.setAttribute("class","lbl");
  t.setAttribute("x",p.x+7);t.setAttribute("y",p.y+3);t.textContent=n.id.replace("app.","");
  nlayer.appendChild(t);
});

function select(id){
  edgeEls.forEach(e=>{
    e.setAttribute("class","edge"+(e.__t===id?" up":e.__s===id?" down":""));
  });
  Object.entries(circles).forEach(([k,c])=>{
    const on=k===id||out[id].has(k)||inc[id].has(k);
    c.style.opacity=on?1:.18;
    c.classList.toggle("sel",k===id);
  });
  const ups=[...inc[id]].sort(), downs=[...out[id]].sort();
  document.getElementById("detail").innerHTML=
    `<h3>${id}</h3>`+
    `<p><b style="color:#fbbf24">上游 ${ups.length}</b>（改它会波及）<br>`+
    (ups.map(x=>`<code>${x.replace("app.","")}</code>`).join(" ")||"<span class=mut>（无，叶子）</span>")+`</p>`+
    `<p><b style="color:#38bdf8">下游 ${downs.length}</b>（它依赖）<br>`+
    (downs.map(x=>`<code>${x.replace("app.","")}</code>`).join(" ")||"<span class=mut>（无）</span>")+`</p>`+
    (dead.has(id)?`<p style="color:#f87171">⚠ 无入边模块（疑似死代码，需人工确认）</p>`:"");
}
svg.addEventListener("click",()=>{
  edgeEls.forEach(e=>e.setAttribute("class","edge"));
  Object.values(circles).forEach(c=>{c.style.opacity=1;c.classList.remove("sel");});
  document.getElementById("detail").innerHTML="";
});
// 缩放/平移
let vb={x:0,y:0,w:Wd,h:Ht};svg.setAttribute("viewBox",`0 0 ${Wd} ${Ht}`);
svg.addEventListener("wheel",e=>{e.preventDefault();const k=e.deltaY<0?.9:1.1;
  const mx=vb.x+vb.w*e.offsetX/svg.clientWidth,my=vb.y+vb.h*e.offsetY/svg.clientHeight;
  vb.w*=k;vb.h*=k;vb.x=mx-(mx-vb.x)*k;vb.y=my-(my-vb.y)*k;
  svg.setAttribute("viewBox",`${vb.x} ${vb.y} ${vb.w} ${vb.h}`);},{passive:false});
let pan=null;
svg.addEventListener("mousedown",e=>{pan={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y};});
window.addEventListener("mousemove",e=>{if(!pan)return;
  vb.x=pan.vx-(e.clientX-pan.x)*vb.w/svg.clientWidth;vb.y=pan.vy-(e.clientY-pan.y)*vb.h/svg.clientHeight;
  svg.setAttribute("viewBox",`${vb.x} ${vb.y} ${vb.w} ${vb.h}`);});
window.addEventListener("mouseup",()=>pan=null);

// 状态栏
const d=P.defects,s=P.stats;
const top=Object.entries(inc).map(([k,v])=>[k,v.size]).sort((a,b)=>b[1]-a[1])[0];
document.getElementById("status").innerHTML=
  `📊 ${P.nodes.length} 模块 · ${P.links.length} IMPORTS 边 · ${s.classes} 类 · ${s.functions} 函数 ｜ `+
  `${d.layer_violations.length?"🔴":"✅"} 跨层违规 ${d.layer_violations.length} · `+
  `${d.cycles.length?"🔴":"✅"} 循环依赖 ${d.cycles.length} · `+
  `${d.dead_modules.length?"🟡":"✅"} 无入边模块 ${d.dead_modules.length} ｜ `+
  `被依赖最多：<code style="background:#0f172a;padding:1px 5px;border-radius:4px;color:#93c5fd">${(top[0]||"").replace("app.","")}</code>（${top[1]||0} 入度）`;
</script></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
