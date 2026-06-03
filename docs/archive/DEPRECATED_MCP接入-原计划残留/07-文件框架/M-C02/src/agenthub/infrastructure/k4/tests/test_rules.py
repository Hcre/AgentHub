"""M-C02 K4 Analyzer - Rules 单元测试.

[文件路径] src/agenthub/infrastructure/k4/tests/test_rules.py
[文件职责] 验证 12 类规则的 match 行为
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02
[测试策略]
  用例数: 36（12 规则 × 3 场景：命中/未命中/边界）
  Mock: 直接构造 ast.Call
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02]
"""
from __future__ import annotations

import ast

import pytest

from agenthub.infrastructure.k4.rules import (
    Rule_DeserializeUntrusted,
    Rule_DynamicImport,
    Rule_EvalExec,
    Rule_HardcodedSecret,
    Rule_PathTraversal,
    Rule_PickleLoad,
    Rule_ShellInject,
    Rule_SQLInject,
    Rule_SubprocessShell,
    Rule_TemplateInject,
    Rule_UnsafeYAML,
    Rule_WeakHash,
)


def _build_call(src: str) -> ast.Call:
    """辅助：解析字符串为 ast.Call（取首节点）."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            return node
    raise ValueError("no Call in source")


# ---------- Rule_PickleLoad ----------


# [测试场景1: 命中 pickle.load]
def test_rule_pickle_load_hit() -> None:
    """pickle.load 应命中."""
    node = _build_call("import pickle; pickle.load(f)")
    assert Rule_PickleLoad().match(node) is not None


# [测试场景2: 未命中]
def test_rule_pickle_load_miss() -> None:
    """json.load 不应命中."""
    node = _build_call("import json; json.load(f)")
    assert Rule_PickleLoad().match(node) is None


# [测试场景3: 边界 cPickle]
def test_rule_pickle_load_cpickle() -> None:
    """cPickle 同样命中."""
    node = _build_call("import cPickle; cPickle.load(f)")
    assert Rule_PickleLoad().match(node) is not None


# ---------- Rule_EvalExec ----------


# [测试场景4: eval 命中]
def test_rule_eval_exec_eval() -> None:
    """eval() 应命中."""
    node = _build_call("eval('1+1')")
    assert Rule_EvalExec().match(node) is not None


# [测试场景5: exec 命中]
def test_rule_eval_exec_exec() -> None:
    """exec() 应命中."""
    node = _build_call("exec('pass')")
    assert Rule_EvalExec().match(node) is not None


# [测试场景6: compile 命中]
def test_rule_eval_exec_compile() -> None:
    """compile() 应命中."""
    node = _build_call("compile('1', '<x>', 'eval')")
    assert Rule_EvalExec().match(node) is not None


# ---------- Rule_ShellInject ----------


# [测试场景7: os.system 命中]
def test_rule_shell_inject_os_system() -> None:
    """os.system 应命中."""
    node = _build_call("import os; os.system('ls')")
    assert Rule_ShellInject().match(node) is not None


# [测试场景8: os.popen 命中]
def test_rule_shell_inject_os_popen() -> None:
    """os.popen 应命中."""
    node = _build_call("import os; os.popen('ls')")
    assert Rule_ShellInject().match(node) is not None


# [测试场景9: 普通函数未命中]
def test_rule_shell_inject_miss() -> None:
    """普通函数不应命中."""
    node = _build_call("foo('ls')")
    assert Rule_ShellInject().match(node) is None


# ---------- Rule_SubprocessShell ----------


# [测试场景10: shell=True 命中]
def test_rule_subprocess_shell_hit() -> None:
    """shell=True 应命中."""
    node = _build_call("subprocess.run('ls', shell=True)")
    assert Rule_SubprocessShell().match(node) is not None


# [测试场景11: shell=False 未命中]
def test_rule_subprocess_shell_miss() -> None:
    """shell=False 不应命中."""
    node = _build_call("subprocess.run(['ls'])")
    assert Rule_SubprocessShell().match(node) is None


# [测试场景12: list 形式未命中]
def test_rule_subprocess_shell_list() -> None:
    """list 形式参数不应命中."""
    node = _build_call("subprocess.call(['ls', '-l'])")
    assert Rule_SubprocessShell().match(node) is None


# ---------- Rule_DynamicImport ----------


# [测试场景13: __import__ 命中]
def test_rule_dynamic_import_hit() -> None:
    """__import__ 应命中."""
    node = _build_call("__import__('os')")
    assert Rule_DynamicImport().match(node) is not None


# [测试场景14: importlib.import_module 命中]
def test_rule_dynamic_import_importlib() -> None:
    """importlib.import_module 应命中."""
    node = _build_call("importlib.import_module('os')")
    assert Rule_DynamicImport().match(node) is not None


# [测试场景15: 普通调用未命中]
def test_rule_dynamic_import_miss() -> None:
    """普通函数不应命中."""
    node = _build_call("foo()")
    assert Rule_DynamicImport().match(node) is None


# ---------- Rule_WeakHash ----------


# [测试场景16: md5 命中]
def test_rule_weak_hash_md5() -> None:
    """md5 应命中."""
    node = _build_call("hashlib.md5(b'x')")
    assert Rule_WeakHash().match(node) is not None


# [测试场景17: sha256 未命中]
def test_rule_weak_hash_sha256_miss() -> None:
    """sha256 不应命中."""
    node = _build_call("hashlib.sha256(b'x')")
    assert Rule_WeakHash().match(node) is None


# [测试场景18: sha1 命中]
def test_rule_weak_hash_sha1() -> None:
    """sha1 应命中."""
    node = _build_call("hashlib.sha1(b'x')")
    assert Rule_WeakHash().match(node) is not None


# ---------- Rule_HardcodedSecret ----------


# [测试场景19: 高熵字符串命中]
def test_rule_hardcoded_secret_hit() -> None:
    """高熵长字符串应命中."""
    tree = ast.parse("API_KEY = 'sk_live_abcdefghij1234567890ABCDEFGHIJ'")
    out: list[object] = []
    for n in ast.walk(tree):
        r = Rule_HardcodedSecret().match(n)
        if r is not None:
            out.append(r)
    assert len(out) >= 1


# [测试场景20: 短字符串未命中]
def test_rule_hardcoded_secret_miss() -> None:
    """短字符串不应命中."""
    node = _build_call("x = 'short'")
    assert Rule_HardcodedSecret().match(node) is None


# [测试场景21: 数字未命中]
def test_rule_hardcoded_secret_number() -> None:
    """纯数字字面量不应命中."""
    tree = ast.parse("PORT = 8080")
    out: list[object] = []
    for n in ast.walk(tree):
        r = Rule_HardcodedSecret().match(n)
        if r is not None:
            out.append(r)
    assert out == []


# ---------- Rule_PathTraversal ----------


# [测试场景22: ../ 命中]
def test_rule_path_traversal_hit() -> None:
    """open('../etc/passwd') 应命中."""
    node = _build_call("open('../etc/passwd')")
    assert Rule_PathTraversal().match(node) is not None


# [测试场景23: 绝对路径未命中]
def test_rule_path_traversal_miss() -> None:
    """open('foo.txt') 不应命中."""
    node = _build_call("open('foo.txt')")
    assert Rule_PathTraversal().match(node) is None


# [测试场景24: Path() 命中]
def test_rule_path_traversal_path() -> None:
    """Path('../x') 应命中."""
    node = _build_call("Path('../x')")
    assert Rule_PathTraversal().match(node) is not None


# ---------- Rule_SQLInject ----------


# [测试场景25: 字符串拼接 execute 命中]
def test_rule_sql_inject_concat() -> None:
    """拼接 SQL 应命中."""
    node = _build_call("cursor.execute('SELECT * FROM t WHERE id=' + uid)")
    assert Rule_SQLInject().match(node) is not None


# [测试场景26: 参数化查询未命中]
def test_rule_sql_inject_param() -> None:
    """参数化查询不应命中."""
    node = _build_call("cursor.execute('SELECT * FROM t WHERE id=%s', (uid,))")
    assert Rule_SQLInject().match(node) is None


# [测试场景27: 字符串模板]
def test_rule_sql_inject_fstring() -> None:
    """f-string SQL 应命中."""
    node = _build_call("cursor.execute(f'SELECT * FROM t WHERE id={uid}')")
    assert Rule_SQLInject().match(node) is not None


# ---------- Rule_DeserializeUntrusted ----------


# [测试场景28: marshal.load 命中]
def test_rule_deserialize_marshal() -> None:
    """marshal.load 应命中."""
    node = _build_call("marshal.load(f)")
    assert Rule_DeserializeUntrusted().match(node) is not None


# [测试场景29: shelve.open 命中]
def test_rule_deserialize_shelve() -> None:
    """shelve.open 应命中."""
    node = _build_call("shelve.open('x')")
    assert Rule_DeserializeUntrusted().match(node) is not None


# [测试场景30: dill.load 命中]
def test_rule_deserialize_dill() -> None:
    """dill.load 应命中."""
    node = _build_call("dill.load(f)")
    assert Rule_DeserializeUntrusted().match(node) is not None


# ---------- Rule_UnsafeYAML ----------


# [测试场景31: yaml.load 无 Loader 命中]
def test_rule_unsafe_yaml_no_loader() -> None:
    """yaml.load 无 Loader 应命中."""
    node = _build_call("yaml.load(stream)")
    assert Rule_UnsafeYAML().match(node) is not None


# [测试场景32: yaml.safe_load 未命中]
def test_rule_unsafe_yaml_safe() -> None:
    """yaml.safe_load 不应命中."""
    node = _build_call("yaml.safe_load(stream)")
    assert Rule_UnsafeYAML().match(node) is None


# [测试场景33: yaml.load SafeLoader 未命中]
def test_rule_unsafe_yaml_safe_loader() -> None:
    """yaml.load(SafeLoader) 不应命中."""
    node = _build_call("yaml.load(stream, Loader=yaml.SafeLoader)")
    assert Rule_UnsafeYAML().match(node) is None


# ---------- Rule_TemplateInject ----------


# [测试场景34: jinja2 autoescape=False 命中]
def test_rule_template_inject_jinja2() -> None:
    """jinja2 Environment(autoescape=False) 应命中."""
    node = _build_call("jinja2.Environment(autoescape=False)")
    assert Rule_TemplateInject().match(node) is not None


# [测试场景35: autoescape=True 未命中]
def test_rule_template_inject_autoescape_true() -> None:
    """autoescape=True 不应命中."""
    node = _build_call("jinja2.Environment(autoescape=True)")
    assert Rule_TemplateInject().match(node) is None


# [测试场景36: Mako Template 命中]
def test_rule_template_inject_mako() -> None:
    """Mako Template 应命中."""
    node = _build_call("mako.template.Template('hello')")
    assert Rule_TemplateInject().match(node) is not None


# ---------- 严重度约束 ----------


@pytest.mark.parametrize(
    "rule_cls",
    [
        Rule_DeserializeUntrusted,
        Rule_DynamicImport,
        Rule_EvalExec,
        Rule_HardcodedSecret,
        Rule_PathTraversal,
        Rule_PickleLoad,
        Rule_ShellInject,
        Rule_SQLInject,
        Rule_SubprocessShell,
        Rule_TemplateInject,
        Rule_UnsafeYAML,
        Rule_WeakHash,
    ],
)
def test_all_rules_severity_in_range(rule_cls: type) -> None:
    """所有规则 severity 必须在 0-100 范围."""
    assert 0 <= rule_cls.severity <= 100
