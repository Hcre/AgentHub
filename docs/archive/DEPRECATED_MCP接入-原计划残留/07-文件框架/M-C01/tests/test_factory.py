"""M-C01 SandboxFactory 测试场景.

[模块编号] M-C01
[文件职责] 覆盖 OS 探测、WSL2 fallback、Docker 兜底、单例缓存.
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008 + TD/TD-003]
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

# TODO(impl): from agenthub.infrastructure.sandbox.factory import SandboxFactory
# TODO(impl): from agenthub.infrastructure.sandbox.backends.linux_cgroup import LinuxCgroupBackend
# TODO(impl): from agenthub.infrastructure.sandbox.backends.macos_sandbox import MacOSSandboxBackend
# TODO(impl): from agenthub.infrastructure.sandbox.backends.windows_jobobj import WindowsJobObjBackend
# TODO(impl): from agenthub.infrastructure.sandbox.backends.docker import DockerBackend


@pytest.fixture(autouse=True)
def _reset_factory_cache():
    """每个测试前重置单例缓存."""
    # TODO(impl): SandboxFactory.reset_cache()
    # TODO(impl): yield
    # TODO(impl): SandboxFactory.reset_cache()
    ...


def test_factory_when_linux_with_cgroup_v2_then_select_linux_cgroup() -> None:
    """场景: Linux + cgroup v2 可用 → LinuxCgroupBackend."""
    # TODO(impl): with patch("platform.system", return_value="Linux"), patch.object(SandboxFactory, "_cgroup_v2_available", return_value=True), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     backend = SandboxFactory.get_backend()
    # TODO(impl): assert isinstance(backend, LinuxCgroupBackend)
    ...


def test_factory_when_macos_then_select_macos_sandbox() -> None:
    """场景: macOS → MacOSSandboxBackend."""
    # TODO(impl): with patch("platform.system", return_value="Darwin"), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     backend = SandboxFactory.get_backend()
    # TODO(impl): assert isinstance(backend, MacOSSandboxBackend)
    ...


def test_factory_when_windows_then_select_windows_jobobj() -> None:
    """场景: Windows → WindowsJobObjBackend."""
    # TODO(impl): with patch("platform.system", return_value="Windows"), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     backend = SandboxFactory.get_backend()
    # TODO(impl): assert isinstance(backend, WindowsJobObjBackend)
    ...


def test_factory_when_wsl2_with_docker_then_fallback_docker() -> None:
    """场景: WSL2 + Docker 可用 → DockerBackend (兜底) [TD:TD-003]."""
    # TODO(impl): with patch.object(SandboxFactory, "_is_wsl2", return_value=True), patch.object(SandboxFactory, "_docker_available", return_value=True):
    # TODO(impl):     backend = SandboxFactory.get_backend()
    # TODO(impl): assert isinstance(backend, DockerBackend)
    ...


def test_factory_when_linux_no_cgroup_v2_and_docker_then_fallback_docker() -> None:
    """场景: Linux 但无 cgroup v2 + 有 Docker → DockerBackend."""
    # TODO(impl): with patch("platform.system", return_value="Linux"), patch.object(SandboxFactory, "_cgroup_v2_available", return_value=False), patch.object(SandboxFactory, "_docker_available", return_value=True):
    # TODO(impl):     backend = SandboxFactory.get_backend()
    # TODO(impl): assert isinstance(backend, DockerBackend)
    ...


def test_factory_when_all_backends_unavailable_then_raise_system_error() -> None:
    """场景: 4 后端均不可用 → SystemError(SANDBOX_BACKEND_UNAVAILABLE)."""
    # TODO(impl): with patch("platform.system", return_value="Linux"), patch.object(SandboxFactory, "_cgroup_v2_available", return_value=False), patch.object(SandboxFactory, "_docker_available", return_value=False), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     with pytest.raises(SystemError) as exc: SandboxFactory.get_backend()
    # TODO(impl): assert exc.value.code == "SANDBOX_BACKEND_UNAVAILABLE"
    ...


def test_factory_when_called_twice_then_return_same_instance() -> None:
    """场景: 同一进程内多次 get_backend → 返回同一实例 (单例缓存)."""
    # TODO(impl): with patch("platform.system", return_value="Linux"), patch.object(SandboxFactory, "_cgroup_v2_available", return_value=True), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     b1 = SandboxFactory.get_backend(); b2 = SandboxFactory.get_backend()
    # TODO(impl): assert b1 is b2
    ...


def test_factory_reset_cache_then_return_fresh_instance() -> None:
    """场景: reset_cache 后再次 get → 新实例."""
    # TODO(impl): with patch("platform.system", return_value="Linux"), patch.object(SandboxFactory, "_cgroup_v2_available", return_value=True), patch.object(SandboxFactory, "_is_wsl2", return_value=False):
    # TODO(impl):     b1 = SandboxFactory.get_backend(); SandboxFactory.reset_cache(); b2 = SandboxFactory.get_backend()
    # TODO(impl): assert b1 is not b2
    ...


def test_factory_cgroup_v2_detection_when_file_missing_then_false() -> None:
    """场景: /sys/fs/cgroup/cgroup.controllers 不存在 → False."""
    # TODO(impl): with patch("pathlib.Path.exists", return_value=False):
    # TODO(impl):     assert SandboxFactory._cgroup_v2_available() is False
    ...


def test_factory_docker_detection_when_docker_missing_then_false() -> None:
    """场景: which("docker") 返回 None → False."""
    # TODO(impl): with patch("shutil.which", return_value=None):
    # TODO(impl):     assert SandboxFactory._docker_available() is False
    ...
