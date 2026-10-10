"""First-use operations: discover, check access, then explicitly create or connect.

No installer, credential store, model task or background scheduler lives here.
"""
from __future__ import annotations

from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

from .gitstore import GitStore, git_env
from .util import Conflict, Error, encode, locked, now, read_json, slug, uid, write_json


ROLES = ("steward", "sentinel", "maintainer")
INSTALL_HELP = {
    "git": "https://git-scm.com/downloads",
    "codex": "https://developers.openai.com/codex/cli",
    "claude": "https://code.claude.com/docs/en/setup",
    "codebuddy": "https://www.codebuddy.ai/docs/cli/overview",
    "workbuddy": "https://www.workbuddy.ai/",
}


def scan():
    """Inspect PATH and conventional macOS app locations, without running a Harness."""
    git = shutil.which("git")
    status = {"state": "missing", "path": git, "install_url": INSTALL_HELP["git"]}
    if git:
        try:
            result = subprocess.run([git, "--version"], stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=5, check=False)
            status.update(state="available" if result.returncode == 0 else "unavailable")
        except (OSError, subprocess.TimeoutExpired):
            status["state"] = "unavailable"
    harnesses = []
    for name, label in (("codex", "Codex"), ("claude", "Claude Code"), ("codebuddy", "CodeBuddy Code")):
        path = shutil.which(name)
        harnesses.append({"id": name + "-cli", "name": label, "entry": "cli", "path": path,
                          "state": "found" if path else "not_found_in_path", "authentication": "unchecked",
                          "adapter": "preview", "sdk": ("not_required" if name == "codex" else
                              "installed" if find_spec(name + "_agent_sdk") else "missing"),
                          "install_url": INSTALL_HELP[name]})
    for name, label in (("codex", "Codex"), ("claude", "Claude"), ("workbuddy", "WorkBuddy")):
        path = None
        if sys.platform == "darwin":
            for directory in (Path("/Applications"), Path.home() / "Applications"):
                candidate = directory / (label + ".app")
                if candidate.is_dir():
                    path = str(candidate)
                    break
        harnesses.append({"id": name + "-desktop", "name": label, "entry": "desktop", "path": path,
                          "state": "found" if path else "location_unconfirmed", "authentication": "unchecked",
                          "adapter": "manual_capture" if name == "codex" else "not_implemented",
                          "install_url": ({"codex": "https://openai.com/index/introducing-the-codex-app/",
                                           "claude": "https://claude.com/download",
                                           "workbuddy": INSTALL_HELP["workbuddy"]})[name]})
    return {"git": status, "harnesses": harnesses, "observed_at": now(),
            "can_create_workspace": status["state"] == "available", "model_invoked": False,
            "guidance": "依赖由用户自行安装和登录，再重新检测。发现程序不代表会话或认证可用。",
            "suggested_first_harness": "codex-cli", "suggestion_status": "preview_not_live_accepted"}


def git_address(address: str) -> tuple[str, bool]:
    """Accept ordinary Git URLs or local paths; reject credentials and remote helpers."""
    if not isinstance(address, str) or not address.strip() or any(ord(c) < 32 for c in address):
        raise Error("请填写有效的 Git 地址或本机目录。")
    address = address.strip()
    if address.startswith("-"):
        raise Error("Git 地址不能以选项前缀开头。")
    if re.match(r"^[A-Za-z]:[\\/]", address):
        return str(Path(address).expanduser().resolve()), False
    if "://" in address:
        url = urllib.parse.urlsplit(address)
        if (url.scheme not in ("https", "ssh") or not url.hostname or url.password is not None
                or (url.scheme == "https" and url.username is not None) or url.query or url.fragment
                or any(c.isspace() for c in address)):
            raise Error("使用不含密码、Token、查询参数的 HTTPS/SSH Git 地址；认证由本机 Git 管理。")
        return address, True
    if re.fullmatch(r"[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[A-Za-z0-9_./~-]+", address):
        return address, True
    if ":" in address:
        raise Error("首次配置使用普通 Git HTTPS/SSH 地址或本机目录，不使用远端 helper 或 github: 简写。")
    return str(Path(address).expanduser().resolve()), False


def instance_directory(app, workspace: str, agent_id: str, directory: str | None = None) -> str:
    """Return one explicit local instance directory without changing identity state.

    Empty values use the installation default. User supplied paths must be absolute so
    a browser form cannot silently reinterpret them relative to the service process.
    """
    slug(workspace)
    slug(agent_id)
    if directory is None or (isinstance(directory, str) and not directory.strip()):
        return str((app.home / "instances" / workspace / agent_id).resolve())
    if not isinstance(directory, str) or any(ord(c) < 32 for c in directory):
        raise Error("实例目录必须是有效的本机绝对路径。")
    value = directory.strip()
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise Error("实例目录必须使用绝对路径；不会相对工作台进程解析。")
    try:
        return str(path.resolve())
    except OSError as exc:
        raise Error("无法规范化实例目录；请检查路径格式和本机权限。") from exc


def instance_directories(app, workspace: str, directories=None) -> dict[str, str]:
    """Normalize the three caretaker destinations and reject ambiguous reuse."""
    if directories is None:
        directories = {}
    if not isinstance(directories, dict):
        raise Error("管家实例目录必须按角色提供。")
    unknown = set(directories) - set(ROLES)
    if unknown:
        raise Error("未知的管家目录角色：" + ", ".join(sorted(unknown)))
    result = {role: instance_directory(app, workspace, role, directories.get(role)) for role in ROLES}
    if len({Path(path) for path in result.values()}) != len(result):
        raise Error("三名管家不能共用同一个实例目录。")
    return result


def check_git(address: str):
    """A read-only probe. Neither success nor an empty repository proves write access."""
    address, remote = git_address(address)
    git = shutil.which("git")
    if not git:
        return {"state": "git_missing", "read_access": "unknown", "write_access": "unchecked",
                "install_url": INSTALL_HELP["git"]}
    if not remote and not Path(address).exists():
        return {"state": "local_target_missing", "read_access": "unknown", "write_access": "unchecked"}
    try:
        with tempfile.TemporaryDirectory(prefix="aw-git-check-") as directory:
            result = subprocess.run([git, "-c", "credential.interactive=false", "ls-remote", "--refs", "--", address],
                                    cwd=directory, env=git_env(), stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=15, check=False)
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "read_access": "unknown", "write_access": "unchecked"}
    except OSError:
        return {"state": "git_unavailable", "read_access": "unknown", "write_access": "unchecked"}
    if result.returncode:
        # Helpers and servers can print secrets. Return an actionable category, never raw stderr.
        return {"state": "unavailable", "read_access": "unconfirmed", "write_access": "unchecked",
                "hint": "请在此用户环境中检查仓库地址、网络、Git 凭据或 SSH 主机信任；工作台不发起登录。"}
    return {"state": "accessible", "read_access": "confirmed", "write_access": "unchecked",
            "empty": not bool(result.stdout.strip()), "remote": remote}


def create_workspace(app, name: str, address: str, mode: str = "local", directories=None):
    """Create three ordinary instances; resume only a previously recorded setup request."""
    slug(name)
    address, remote = git_address(address)
    if mode not in ("local", "remote", "connect") or (mode == "local" and remote):
        raise Error("请选择创建本机、初始化空远端或接入已有 Workspace。")
    if not shutil.which("git"):
        raise Error("请先自行安装 Git，再重新打开工作台检测。")
    existing_alias = app.local()["workspaces"].get(name)
    if existing_alias and existing_alias["address"] != address:
        raise Conflict("这个简称已连接到另一地址；请使用新的简称。")
    if mode == "connect":
        if directories:
            raise Error("接入已有 Workspace 不重建管家；接入后再为选定实例准备本机目录。")
        try:
            result = app.workspace_connect(name, address)
        except (Error, OSError, ValueError, subprocess.TimeoutExpired):
            raise Error("接入失败：请检查 Git 访问、仓库格式和本机权限；未创建或启动实例。") from None
        return {**result, "state": "connected", "instances_created": [], "sessions_started": False,
                "write_access": "unchecked"}
    selected_directories = instance_directories(app, name, directories)
    receipt_path = app.home / "setup" / f"{name}.json"
    with locked(receipt_path.with_suffix(".lock"), wait=0):
        receipt = read_json(receipt_path)
        if receipt and (receipt["address"], receipt["mode"]) != (address, mode):
            raise Conflict("已有不同的创建记录；请使用原地址继续，或另选简称。")
        if receipt:
            saved_directories = receipt.get("directories")
            if saved_directories is None:
                saved_directories = instance_directories(app, name)
                receipt["directories"] = saved_directories
                write_json(receipt_path, receipt)
            if saved_directories != selected_directories:
                raise Conflict("已有创建记录采用另一组实例目录；请沿用原路径继续，不会迁移或复制已有结果。")
        if not receipt:
            if existing_alias:
                raise Conflict("这是已接入的 Workspace，不能用初始化重建；请直接打开工作台。")
            if mode == "local":
                target = Path(address)
                if target.exists() and (not target.is_dir() or any(target.iterdir())):
                    raise Conflict("新建本机 Workspace 需要空目录；已有空间请使用接入。")
            else:
                check = check_git(address)
                if check.get("state") != "accessible" or not check.get("empty"):
                    raise Error("请先准备可读取的空 Git 仓库。读取成功不代表已获写权限。")
            definitions = files("agent_workspace") / "resources" / "definitions"
            receipt = {"id": uid("setup"), "address": address, "mode": mode, "created_at": now(),
                       "directories": selected_directories,
                       "definitions": {role: (definitions / (role + ".md")).read_text(encoding="utf-8")
                                       for role in ROLES}}
            write_json(receipt_path, receipt)
        stage, completed = "workspace", []
        try:
            if mode == "local":
                target = Path(address)
                if not target.exists() or not any(target.iterdir()):
                    GitStore.initialize(target)
                # An interrupted initialization may have left an empty bare repository.
                result = subprocess.run(["git", "--git-dir", address, "rev-parse", "--is-bare-repository"],
                                        capture_output=True, timeout=5, check=False)
                if result.returncode or result.stdout.strip() != b"true":
                    raise Conflict("创建位置不再是预期的 bare Git 仓库；没有覆盖其内容。")
            store = GitStore(address, app.home)
            snap = store.snapshot()
            if not snap.revision:
                check = check_git(address)
                if check.get("state") != "accessible" or not check.get("empty"):
                    raise Conflict("目标仓库已有其他引用或不可访问；不会在非空仓库初始化。")
                metadata = {"schema": 1, "name": name, "locator": "workspace:" + receipt["id"],
                            "friends": {}, "projects": {}, "setup_id": receipt["id"],
                            "caretakers": {role: role for role in ROLES}}
                seed = {"workspace.json": encode(metadata)}
                seed.update({f"definitions/caretaker/{role}/definition.md": text.encode()
                             for role, text in receipt["definitions"].items()})
                store.branch("main", seed)
                snap = store.snapshot()
            metadata = snap.json("workspace.json", {})
            if metadata.get("setup_id") != receipt["id"]:
                raise Conflict("远端不是本次创建的 Workspace；请使用接入，不能覆盖或接管。")
            if not receipt.get("definition_revision"):
                receipt["definition_revision"] = snap.revision
                write_json(receipt_path, receipt)
            app.workspace_connect(name, address)
            for role in ROLES:
                stage = "caretaker/" + role
                item = app.create(name, role, agent_id=role, definition=f"definitions/caretaker/{role}",
                                  revision=receipt["definition_revision"], request_id=receipt["id"] + "-" + role,
                                  directory=receipt["directories"][role])
                completed.append({"role": role, "id": item["id"], "directory": item["directory"],
                                  "revision": item["revision"]})
            receipt["completed"] = True
            write_json(receipt_path, receipt)
            return {"name": name, "state": "created", "caretakers": completed,
                    "directories": dict(receipt["directories"]), "sessions_started": False,
                    "monitoring_changed": False, "configuration": "choose_per_instance",
                    "hint": "三份身份已建立或复用，并在所选本机目录准备实例资产。本次没有启动模型或修改巡检状态。"}
        except (Error, OSError, subprocess.TimeoutExpired) as exc:
            return {"name": name, "state": "pending", "stage": stage, "caretakers": completed,
                    "directories": dict(receipt["directories"]),
                    "code": getattr(exc, "code", "operation_failed"), "sessions_started": False,
                    "hint": "创建未全部完成，已有结果保留。用相同地址、方式和实例目录继续；遇到冲突不要覆盖。"}


def init_workspace(app, name, directory):
    return create_workspace(app, name, directory, mode="local")


def prepare_instance(app, workspace, agent_id, directory=None):
    """Explicitly materialize a selected existing identity without taking execution rights."""
    slug(workspace)
    slug(agent_id)
    locations = app.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
    selected = instance_directory(app, workspace, agent_id, directory) if directory else (
        locations[0] if locations else instance_directory(app, workspace, agent_id))
    return {**app.connect_agent(workspace, agent_id, selected), "sessions_started": False}
