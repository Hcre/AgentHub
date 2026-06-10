"""版本历史端点测试：file-history / file-at-rev / file-write。

现造一个临时 git repo（2 次提交同一文件），验证历史、按版本取内容、回写覆盖。
"""

from __future__ import annotations

import base64
import os
import subprocess

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import importlib.util as _ilu

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_spec = _ilu.spec_from_file_location("_skills_mod_v", "app/api/routers/skills.py")
_skills_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_skills_mod)

_GIT = bool(__import__("shutil").which("git"))
pytestmark = pytest.mark.skipif(not _GIT, reason="git 未安装")


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(_skills_mod.FS_ROUTER)
    return TestClient(app)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    _git(d, "init")
    _git(d, "config", "user.email", "t@t.com")
    _git(d, "config", "user.name", "t")
    f = d / "code.py"
    f.write_text("v1 content\n", encoding="utf-8")
    _git(d, "add", "code.py")
    _git(d, "commit", "-m", "first")
    f.write_text("v2 content\n", encoding="utf-8")
    _git(d, "add", "code.py")
    _git(d, "commit", "-m", "second")
    return str(f)


def test_file_history_lists_commits(client: TestClient, repo) -> None:
    resp = client.get("/api/fs/file-history", params={"path": repo})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["count"] == 2
    subjects = [c["subject"] for c in data["commits"]]
    assert subjects == ["second", "first"]  # newest first
    assert all(len(c["sha"]) == 40 for c in data["commits"])


def test_file_at_rev_returns_old_content(client: TestClient, repo) -> None:
    hist = client.get("/api/fs/file-history", params={"path": repo}).json()
    first_sha = hist["commits"][-1]["sha"]
    resp = client.get("/api/fs/file-at-rev", params={"path": repo, "rev": first_sha})
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "v1 content\n"


def test_file_at_rev_bad_rev_422(client: TestClient, repo) -> None:
    resp = client.get("/api/fs/file-at-rev", params={"path": repo, "rev": "not-a-sha!"})
    assert resp.status_code == 422


def test_file_write_overwrites_existing(client: TestClient, repo) -> None:
    resp = client.post("/api/fs/file-write", json={"path": repo, "content": "restored\n"})
    assert resp.status_code == 200, resp.text
    with open(repo, encoding="utf-8") as f:
        assert f.read() == "restored\n"


def test_file_write_rejects_nonexistent(client: TestClient, tmp_path) -> None:
    resp = client.post(
        "/api/fs/file-write",
        json={"path": str(tmp_path / "nope.py"), "content": "x"},
    )
    assert resp.status_code == 404


def test_file_history_non_git_graceful(client: TestClient, tmp_path) -> None:
    f = tmp_path / "lonely.txt"
    f.write_text("hi", encoding="utf-8")
    resp = client.get("/api/fs/file-history", params={"path": str(f)})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
