"""Verifier 机械验收测试（coordinator-test-plan §4）。

命门 TC-4.1：worker 自称完成但验收命令失败 → Verdict(passed=False)。
含修正后的行为：非 mechanical fail-closed、无 cwd fail-fast、invalid expect 守卫。
"""

from __future__ import annotations

import pytest

from app.domain.task_engine.dag import Check, TaskDef, TaskNode
from app.domain.task_engine.verifier import MechanicalVerifier


def _node(task_id="t1", acceptance=None, worktree=None, no_verify=False) -> TaskNode:
    task = TaskDef(
        id=task_id,
        title=task_id,
        suggested_worker="w",
        acceptance=acceptance if acceptance is not None else [Check("mechanical", "true")],
        no_verify=no_verify,
    )
    return TaskNode(task=task, worktree=worktree)


def _v(workspace=".") -> MechanicalVerifier:
    return MechanicalVerifier(workspace=workspace)


# --- TC-4.1 命门：说谎 worker 被 Verifier 抓 ---


@pytest.mark.asyncio
async def test_lying_worker_caught() -> None:
    node = _node(acceptance=[Check("mechanical", "false")])  # exit 1
    result = await _v().verify(node)
    assert not result.passed
    assert "实际 1" in result.reason


@pytest.mark.asyncio
async def test_honest_worker_passes() -> None:
    result = await _v().verify(_node(acceptance=[Check("mechanical", "true")]))
    assert result.passed


# --- TC-4.3 / 4.4 多 check ---


@pytest.mark.asyncio
async def test_multi_checks_all_pass() -> None:
    node = _node(acceptance=[Check("mechanical", "true")] * 3)
    assert (await _v().verify(node)).passed


@pytest.mark.asyncio
async def test_multi_checks_second_fails() -> None:
    node = _node(acceptance=[
        Check("mechanical", "true"),
        Check("mechanical", "false"),
        Check("mechanical", "true"),
    ])
    result = await _v().verify(node)
    assert not result.passed
    assert "false" in result.reason  # 指向第二条


# --- TC-4.5 超时 ---


@pytest.mark.asyncio
async def test_command_timeout(monkeypatch) -> None:
    import app.domain.task_engine.verifier as mod

    monkeypatch.setattr(mod, "CHECK_TIMEOUT", 1)
    result = await _v().verify(_node(acceptance=[Check("mechanical", "sleep 5")]))
    assert not result.passed
    assert "超时" in result.reason


# --- TC-4.6 修正：命令不存在 → exit 127（非 OSError） ---


@pytest.mark.asyncio
async def test_nonexistent_command_fails() -> None:
    node = _node(acceptance=[Check("mechanical", "nonexistent_cmd_xyz_123")])
    result = await _v().verify(node)
    assert not result.passed  # shell 返回 127


# --- OSError 路径：cwd 不存在 ---


@pytest.mark.asyncio
async def test_bad_cwd_raises_oserror() -> None:
    v = MechanicalVerifier(workspace="/nonexistent_dir_xyz_987")
    result = await v.verify(_node(acceptance=[Check("mechanical", "true")]))
    assert not result.passed
    assert "无法执行" in result.reason


# --- TC-4.7 / 4.8 expect ---


@pytest.mark.asyncio
async def test_expect_match() -> None:
    node = _node(acceptance=[Check("mechanical", "bash -c 'exit 2'", expect="2")])
    assert (await _v().verify(node)).passed


@pytest.mark.asyncio
async def test_expect_mismatch() -> None:
    node = _node(acceptance=[Check("mechanical", "bash -c 'exit 1'", expect="0")])
    assert not (await _v().verify(node)).passed


@pytest.mark.asyncio
async def test_invalid_expect_rejected() -> None:
    node = _node(acceptance=[Check("mechanical", "true", expect="abc")])
    result = await _v().verify(node)
    assert not result.passed
    assert "无效 expect" in result.reason


# --- TC-4.9 no_verify ---


@pytest.mark.asyncio
async def test_no_verify_passes() -> None:
    node = _node(acceptance=[], no_verify=True)
    result = await _v().verify(node)
    assert result.passed
    assert "no_verify" in result.reason


# --- TC-4.10 在工作目录内跑 ---


@pytest.mark.asyncio
async def test_runs_in_worktree(tmp_path) -> None:
    wt = tmp_path / "wt1"
    wt.mkdir()
    node = _node(acceptance=[Check("mechanical", "pwd")], worktree=str(wt))
    assert (await _v().verify(node)).passed


# --- 修正：非 mechanical → fail-closed（不静默通过，§6.1） ---


@pytest.mark.asyncio
async def test_llm_judge_fail_closed() -> None:
    node = _node(acceptance=[Check("llm_judge", "检查错误提示是否中文")])
    result = await _v().verify(node)
    assert not result.passed
    assert "不支持" in result.reason


# --- 修正：无 cwd → fail-fast（不在 server cwd 跑） ---


@pytest.mark.asyncio
async def test_no_cwd_fail_fast() -> None:
    v = MechanicalVerifier(workspace=None)
    node = _node(acceptance=[Check("mechanical", "true")], worktree=None)
    result = await v.verify(node)
    assert not result.passed
    assert "工作目录" in result.reason
