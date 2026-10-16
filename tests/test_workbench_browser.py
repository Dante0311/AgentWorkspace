"""Three Workbench views through real local HTTP and Chromium.

Git data and backend observations are isolated fixtures. No native model or
Desktop session is opened; explicit backend protocol fixtures are named below.
"""
import json
import os
import sys
import threading

import pytest

from agent_workspace.direct_messages import DirectMessages
from agent_workspace.messages import Messages
from agent_workspace.server import make_server
from agent_workspace.util import write_json


@pytest.fixture(scope="module")
def browser():
    if not (os.environ.get("AW_BROWSER_TESTS") == "1" or os.environ.get("AW_TEST_BROWSER")):
        pytest.skip("Set AW_BROWSER_TESTS=1 or AW_TEST_BROWSER to run real browser integration")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as api:
        options = {"headless": True}
        if os.environ.get("AW_TEST_BROWSER"):
            options["executable_path"] = os.environ["AW_TEST_BROWSER"]
        instance = api.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture
def ui(pair, browser):
    app, bindings = pair
    server = make_server(app, 0, "browser-test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    page.set_default_timeout(60000)
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page.goto(base + "/#token=browser-test-token")
        page.wait_for_selector("#app:not(.hidden)")
        yield app, bindings, page
        assert not failures, failures
    finally:
        try:
            context.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
            assert not thread.is_alive()


def nav(page, view):
    if page.viewport_size["width"] < 700:
        page.locator("#mobile-menu").click()
    page.locator(f'[data-view="{view}"]').click()
    page.wait_for_function("!busy")


def pending(page):
    return page.evaluate("pendingMessage()")


def store_pending(page, bindings, request_id):
    value = {"locator": page.evaluate("wsMeta().locator"), "args": {
        "workspace": "sea", "agent_id": "alice", "binding": bindings["alice"],
        "to": "bob", "content": "original message", "request_id": request_id,
        "delivery": "normal",
    }}
    page.evaluate("value => {sessionStorage.setItem(pendingKey(), JSON.stringify(value)); render()}", value)
    return value


def backend_fixture(page, control=None):
    """HTTP boundary fixture, not evidence that an OS process started or exited."""
    observed = {"running": True, "ready": True, "pid": 101, "observed_at": "fixture-read-time"}
    calls = []

    def route(request):
        name = request.request.post_data_json["command"]
        if not name.startswith("backend."):
            request.continue_()
            return
        calls.append(name)
        if name == "backend.status":
            result = dict(observed)
        elif name == "backend.log":
            result = {"content": "fixture backend log"}
        else:
            result = control(name, observed) if control else {"state": "stop_requested"}
        request.fulfill(json={"ok": True, "result": result})

    page.route("**/api/execute", route)
    return calls, observed


def test_primary_navigation_has_three_views_and_keeps_identity_distinct(ui):
    app, bindings, page = ui
    assert page.locator("[data-view]").evaluate_all("items => items.map(item => item.dataset.view)") == ["agents", "messages", "backend"]
    assert page.locator("article.agent-row").count() == 2
    assert page.get_by_role("button", name="创建 Agent", exact=True).count() == 0
    page.locator("article.agent-row").filter(has_text="alice").locator(".agent-name").click()
    assert page.get_by_role("heading", name="当前执行会话", exact=True).is_visible()
    assert page.get_by_role("heading", name="历史执行会话", exact=True).is_visible()
    assert "native-alice" in page.locator("dl.kv").first.inner_text()
    assert app.agent("sea", "alice")["current"] == bindings["alice"]


def test_refresh_reads_external_messages_and_ack(ui):
    app, bindings, page = ui
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "First", request_id="refresh-first")
    nav(page, "messages")
    page.locator('[data-action="message-show"][data-id="refresh-first"]').first.wait_for()
    messages.receive("sea", "bob", bindings["bob"], "refresh-first")
    messages.send("sea", "bob", bindings["bob"], "alice", "Second", request_id="refresh-second")
    page.locator("#refresh").click()
    page.wait_for_function("document.querySelectorAll('article.table-row').length === 2", timeout=15000)
    first = page.locator("article.table-row").filter(has_text="refresh-first")
    assert first.get_by_text("已确认通知", exact=True).is_visible()
    assert len(messages.list("sea")) == 2


def test_agent_scope_includes_inbound_and_outbound_without_replacing_workspace(ui):
    app, bindings, page = ui
    messages = Messages(app)
    for sender, receiver, identifier in [("alice", "bob", "scope-out"), ("bob", "alice", "scope-in"), ("bob", "bob", "scope-other")]:
        messages.send("sea", sender, bindings[sender], receiver, identifier, request_id=identifier)
    page.locator("article.agent-row").filter(has_text="alice").locator(".agent-name").click()
    page.get_by_role("button", name="查看此 Agent 的消息", exact=True).click()
    page.wait_for_function("!busy")
    assert page.locator("article.table-row").count() == 2
    page.locator("#message-direction").select_option("in")
    assert page.locator("article.table-row").count() == 1
    assert page.locator('[data-id="scope-in"]').first.is_visible()
    nav(page, "messages")
    assert page.locator("#message-agent").input_value() == ""
    assert page.locator("article.table-row").count() == 3


@pytest.mark.parametrize("observation", ["missing", "damaged"])
def test_agent_detail_does_not_turn_unknown_observation_into_stopped(ui, observation):
    app, bindings, page = ui
    if observation == "missing":
        app.change_local(lambda registry: registry["workspaces"]["sea"]["instances"].pop("alice"))
        expected = "本机无副本，未观测"
    else:
        (app.root("sea", "alice") / ".agentworkspace/local/runtime/status.json").write_bytes(b"{broken")
        expected = "本机状态读取失败"
    page.locator("#refresh").click()
    page.wait_for_function("!document.getElementById('refresh').disabled")
    page.locator("article.agent-row").filter(has_text="alice").locator(".agent-name").click()
    facts = page.locator("dl.kv").first.inner_text()
    assert expected in facts
    assert "未运行" not in facts and "关闭" not in facts
    assert bindings["alice"] in facts
    assert app.agent("sea", "alice")["current"] == bindings["alice"]


@pytest.mark.parametrize("damaged_old_copy", [False, True])
def test_current_copy_is_not_replaced_by_stale_copy_and_history_is_separate(ui, tmp_path, damaged_old_copy):
    app, bindings, page = ui
    first = app.root("sea", "alice")
    old = bindings["alice"]
    point = app.checkpoint("sea", "alice", "saved", binding=old, checkpoint_id="copy-point")
    app.stop("sea", "alice", old, point["id"])
    app.finish_stop("sea", "alice", old, observed_idle=True)
    second = tmp_path / "second-copy"
    app.connect_agent("sea", "alice", second)
    current = app.reserve("sea", "alice", second)["binding"]
    app.bind("sea", "alice", current, "fixture-current-session", second)
    write_json(first / ".agentworkspace/local/runtime/status.json", {"binding": old, "session": "native-alice", "state": "fixture-old-busy"})
    if damaged_old_copy:
        (first / ".agentworkspace/local/runtime/status.json").write_bytes(b"{broken")
    write_json(second / ".agentworkspace/local/runtime/status.json", {"binding": current, "session": "fixture-current-session", "state": "fixture-current-idle"})
    page.locator("#refresh").click()
    page.wait_for_function("!document.getElementById('refresh').disabled")
    assert page.locator("#agent-count").inner_text() == "2"
    page.locator("article.agent-row").filter(has_text="alice").locator(".agent-name").click()
    facts = page.locator("dl.kv").first.inner_text()
    assert "fixture-current-idle" in facts and "fixture-old-busy" not in facts
    copies = page.locator("section.card").filter(has=page.get_by_role("heading", name="本地副本", exact=True))
    old_copy = copies.locator("article.operation").filter(has_text=str(first)).inner_text()
    assert ("此副本的本机状态读取失败" if damaged_old_copy else "fixture-old-busy") in old_copy
    assert page.get_by_text("历史执行入口", exact=True).count() == 1
    assert page.get_by_text("来源登记不证明原生会话当前仍在该机器执行", exact=True).is_visible()


def test_direct_records_are_labeled_without_formal_ack_or_failure(ui):
    app, bindings, page = ui
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "Formal", request_id="formal-history")
    direct = DirectMessages(app).record("sea", "alice", bindings["alice"], "bob", "Native record only", request_id="native-history")
    assert direct["recorded"] is True
    nav(page, "messages")
    assert page.locator("article.table-row").count() == 2
    row = page.locator("article.table-row").filter(has_text="native-history")
    assert row.get_by_text("Codex 直发记录", exact=True).is_visible()
    assert row.get_by_text("未保存可选回执", exact=True).is_visible()
    assert "首次留档时间" in row.inner_text() and "发送失败" not in row.inner_text()
    row.get_by_role("button", name="查看", exact=True).click()
    page.wait_for_selector("#result:not(.hidden)")
    assert json.loads(page.locator("#result-output").inner_text())["record"]["content"] == "Native record only"
    assert [record["id"] for record in messages.list("sea")] == ["formal-history"]
    snap = app.store("sea").snapshot()
    assert "message-index/native-history.json" not in snap.entries
    assert "acks/native-history.json" not in snap.entries


@pytest.mark.parametrize("published", [False, True])
def test_old_unknown_message_keeps_original_id_when_response_is_lost(ui, published):
    app, bindings, page = ui
    identifier = "original-pending"
    value = store_pending(page, bindings, identifier)
    if published:
        Messages(app).send(**value["args"])
    sends = []

    def lose_reply(route):
        if route.request.post_data_json["command"] == "message.send":
            sends.append(route.request.post_data_json["arguments"])
            response = route.fetch().json()
            route.abort()
            assert response["ok"], response
        else:
            route.continue_()

    page.route("**/api/execute", lose_reply)
    page.get_by_role("button", name="继续原请求", exact=True).click()
    page.wait_for_function("!busy")
    if not published:
        assert pending(page)["args"]["request_id"] == identifier
        page.unroute("**/api/execute", lose_reply)
        page.get_by_role("button", name="继续原请求", exact=True).click()
        page.wait_for_function("!busy")
    assert pending(page) is None
    assert len(sends) == (0 if published else 1)
    assert [record["id"] for record in Messages(app).list("sea")] == [identifier]
    assert not app.store("sea").snapshot().json(f"acks/{identifier}.json")


def test_corrupt_pending_record_is_retained_without_replay(ui):
    app, _, page = ui
    page.evaluate("sessionStorage.setItem(pendingKey(), '{broken'); render()")
    assert "旧消息请求不可读" in page.locator("#pending-operation").inner_text()
    assert page.evaluate("sessionStorage.getItem(pendingKey())") == "{broken"
    assert Messages(app).list("sea") == []


def test_backend_stop_acceptance_is_not_shown_as_actual_exit(ui):
    _, _, page = ui
    calls, _ = backend_fixture(page)
    nav(page, "backend")
    page.get_by_role("button", name="请求停止", exact=True).click()
    page.wait_for_function("!busy")
    assert page.get_by_text("本机后台已就绪", exact=True).is_visible()
    assert "尚需确认实际退出" in page.locator("#content").inner_text()
    assert calls.count("backend.stop") == 1
    assert not page.locator("#result:not(.hidden)").is_visible()


def test_backend_restart_reads_new_process_without_repeating_control(ui):
    _, _, page = ui

    def control(name, observed):
        assert name == "backend.restart"
        observed.update(pid=202)
        return {"state": "restart_requested"}

    calls, _ = backend_fixture(page, control)
    nav(page, "backend")
    page.get_by_role("button", name="请求重启", exact=True).click()
    page.wait_for_function("!busy")
    assert "观察到新的后台进程就绪" in page.locator("#content").inner_text()
    assert calls.count("backend.restart") == 1
    assert calls.count("backend.status") >= 2
    assert not page.locator("#result:not(.hidden)").is_visible()


def test_message_source_failure_does_not_claim_empty_complete_history(ui):
    _, _, page = ui

    def fail_direct(route):
        if route.request.post_data_json["command"] == "direct-message.list":
            route.fulfill(status=500, json={"ok": False, "error": "fixture unreadable direct records"})
        else:
            route.continue_()

    page.route("**/api/execute", fail_direct)
    nav(page, "messages")
    assert page.get_by_role("heading", name="历史尚未完整读取", exact=True).is_visible()
    assert "不能据此判定另一来源没有消息" in page.locator("#content").inner_text()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 960}])
def test_three_views_and_recovery_fit_viewport(ui, viewport, tmp_path):
    _, bindings, page = ui
    page.set_viewport_size(viewport)
    backend_fixture(page)
    store_pending(page, bindings, "layout-pending-with-a-long-original-identifier")
    for view in ("agents", "messages", "backend"):
        nav(page, view)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), view
        page.screenshot(path=str(tmp_path / f"workbench-{viewport['width']}-{view}.png"), full_page=True, animations="disabled")
    page.get_by_role("button", name="读取日志", exact=True).click()
    page.wait_for_function("!busy")
    assert "fixture backend log" in page.locator("#backend-log").inner_text()
    page.get_by_role("button", name="查看原请求", exact=True).click()
    page.wait_for_function("!busy")
    assert page.locator("#result:not(.hidden)").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_ordinary_page_without_workspace_lost_response_does_not_open_twice(tmp_path, browser, monkeypatch):
    from agent_workspace.app import App
    from agent_workspace import sessions

    app = App(tmp_path / "empty-home")
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("unchanged project rules", encoding="utf-8")
    launches = []

    def terminal(argv):
        launches.append(argv)
        return [sys.executable, "-c", "pass"], {}

    monkeypatch.setattr(sessions, "_terminal", terminal)
    server = make_server(app, 0, "ordinary-browser-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/sessions#token=ordinary-browser-token")
        page.wait_for_selector("#app:not([hidden])")
        page.locator("#kind").select_option("claude")
        page.locator("#directory").fill(str(project))
        page.locator("#executable").fill(sys.executable)
        page.locator("#prompt").fill("Review only; no project file change.")

        def lose_response(route):
            if route.request.post_data_json["command"] == "session.open":
                assert route.fetch().json()["ok"]
                route.abort()
            else:
                route.continue_()

        page.route("**/api/execute", lose_response)
        page.locator("#form").evaluate("f => { f.requestSubmit(); f.requestSubmit(); }")
        page.wait_for_function("!busy && !!document.getElementById('error').textContent")
        assert len(launches) == 1
        page.unroute("**/api/execute", lose_response)
        page.reload()
        page.wait_for_selector("#pending:not([hidden])")
        page.locator("#continue").click()
        page.wait_for_function("!busy")
        assert len(launches) == 1 and not app.registry.exists()
        assert len(list((app.home / "ordinary-sessions").glob("*.json"))) == 1
        assert (project / "AGENTS.md").read_text() == "unchanged project rules"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_first_use_page_creates_caretakers_in_selected_directories(tmp_path, browser):
    from agent_workspace.app import App

    app = App(tmp_path / "fresh-home")
    repository = tmp_path / "team.git"
    directories = {
        "steward": tmp_path / "agents" / "steward",
        "sentinel": tmp_path / "other-volume" / "sentinel",
        "maintainer": tmp_path / "agents" / "maintainer",
    }
    server = make_server(app, 0, "setup-browser-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(60000)
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/setup#token=setup-browser-token")
        page.wait_for_selector("#app:not(.hidden)")
        page.locator("#name").fill("team")
        page.locator("#address").fill(str(repository))
        for role, directory in directories.items():
            page.locator(f"#dir-{role}").fill(str(directory))
        page.locator("#create").click()
        page.wait_for_function("""document.getElementById('output').textContent.includes('"state": "created"')""")
        for role, directory in directories.items():
            assert app.root("team", role) == directory.resolve()
            assert app.agent("team", role)["current"] is None
        page.wait_for_function("!busy && document.getElementById('workspace').value === 'team'")
        assert page.locator("#workspace").input_value() == "team"
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_selector("#app:not(.hidden)")
        assert page.locator("article.agent-row").count() == 3
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("native_host", ["local", "other-host"])
def test_native_session_confirmation_requires_explicit_read_and_actual_host(ui, monkeypatch, native_host):
    from unittest.mock import Mock
    from agent_workspace import runtime

    app, _, page = ui
    app.create("sea", "desktop-fixture")
    root = app.root("sea", "desktop-fixture")
    app.configure("sea", "desktop-fixture", {"kind": "desktop", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "desktop-fixture")["binding"]
    app.bind("sea", "desktop-fixture", binding, "fixture-native-id")
    peer = Mock()
    peer.tools = {"read_thread", "send_message_to_thread"}
    peer.read.return_value = {"thread": {"id": "fixture-native-id", "hostId": native_host,
                                       "cwd": str(root), "status": {"type": "active"}}}
    constructor = Mock(return_value=peer)
    monkeypatch.setattr(runtime, "Desktop", constructor)
    page.locator("#refresh").click()
    page.wait_for_function("!document.getElementById('refresh').disabled")
    page.locator("article.agent-row").filter(has_text="desktop-fixture").locator(".agent-name").click()
    constructor.assert_not_called()
    page.get_by_role("button", name="核对本机原生会话", exact=True).click()
    page.wait_for_function("!busy")
    expected = "该次核对确认了本机原生会话" if native_host == "local" else "该次核对未确认当前本机原生会话"
    assert page.get_by_text(expected, exact=True).is_visible()
    peer.read.assert_called_once()
    peer.notify.assert_not_called()
    peer.create.assert_not_called()
    peer.close.assert_called_once()



def test_backend_unknown_lock_status_is_not_displayed_as_stopped(ui):
    _, _, page = ui
    _, observed = backend_fixture(page)
    observed.update(state="unknown", ready=False, unknown_reason="fixture unreadable control endpoint")
    nav(page, "backend")
    assert page.get_by_text("后台锁仍被占用，实际状态未知", exact=True).is_visible()
    assert page.get_by_text("本机后台未运行", exact=True).count() == 0


def test_backend_log_retains_registered_source_on_refresh_and_clears_on_change(ui):
    app, _, page = ui
    calls = []

    def route(request):
        body = request.request.post_data_json
        if body["command"] == "backend.status":
            result = {"running": True, "ready": True, "pid": 101}
        elif body["command"] == "backend.log":
            calls.append(body["arguments"])
            result = {"source": {"kind": "runner"}, "exists": True, "content": "REGISTERED_COPY_LOG_MARKER", "observed_at": "fixture-log-time"}
        else:
            request.continue_()
            return
        request.fulfill(json={"ok": True, "result": result})

    page.route("**/api/execute", route)
    nav(page, "backend")
    page.locator("#log-source").select_option(index=1)
    selected = page.locator("#log-source").input_value()
    page.get_by_role("button", name="读取日志", exact=True).click()
    page.wait_for_function("!busy")
    assert calls == [{"workspace": "sea", "agent_id": "alice", "directory": str(app.root("sea", "alice"))}]
    assert "REGISTERED_COPY_LOG_MARKER" in page.locator("#backend-log").inner_text()
    page.locator("#refresh").click()
    page.wait_for_function("!document.getElementById('refresh').disabled")
    assert page.locator("#log-source").input_value() == selected
    assert "REGISTERED_COPY_LOG_MARKER" in page.locator("#backend-log").inner_text()
    page.locator("#log-source").select_option("")
    assert "尚未读取此来源" in page.locator("#backend-log").inner_text()


def test_real_backend_browser_restart_stop_and_reconnect_without_workspace(tmp_path, browser, monkeypatch):
    """Real isolated OS backend and HTTP/browser, without Agent or model tasks."""
    import time
    import subprocess
    from pathlib import Path
    from agent_workspace.app import App
    from agent_workspace import backend
    from agent_workspace.util import read_json

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "src"))
    app = App(tmp_path / "isolated-backend-home")

    def wait_status(predicate):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = backend.status(app)
            if predicate(result):
                return result
            time.sleep(0.2)
        pytest.fail("Isolated backend did not reach the expected actual status")

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(30000)
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    try:
        started = backend.start(app, port=0)
        assert started["ready"] and started["running"]
        original_pid = started["pid"]
        connection = read_json(app.home / "backend/connection.json")
        page.goto(started["url"] + "#token=" + connection["token"])
        page.wait_for_selector("#app:not(.hidden)")
        assert page.get_by_role("heading", name="尚未接入 Workspace", exact=True).is_visible()
        nav(page, "backend")
        assert page.get_by_text("本机后台已就绪", exact=True).is_visible()
        page.get_by_role("button", name="启动后台", exact=True).click()
        page.wait_for_function("!busy")
        assert backend.status(app)["pid"] == original_pid
        assert page.locator("#result").get_attribute("class").split().count("hidden") == 1

        with (app.home / "backend/backend.log").open("a", encoding="utf-8") as output:
            output.write("ISOLATED_BACKEND_BROWSER_MARKER\n")
        page.get_by_role("button", name="读取日志", exact=True).click()
        page.wait_for_function("!busy")
        assert "ISOLATED_BACKEND_BROWSER_MARKER" in page.locator("#backend-log").inner_text()

        page.get_by_role("button", name="请求重启", exact=True).click()
        page.wait_for_function("!busy", timeout=30000)
        restarted = wait_status(lambda result: result.get("ready") and result.get("pid") != original_pid)
        assert "观察到新的后台进程就绪" in page.locator("#content").inner_text()
        assert page.evaluate("backendState.pid") == restarted["pid"]
        assert restarted["url"] == started["url"]
        assert read_json(app.home / "backend/connection.json")["token"] == connection["token"]
        assert page.locator("#result").get_attribute("class").split().count("hidden") == 1

        page.get_by_role("button", name="请求停止", exact=True).click()
        page.wait_for_function("!busy")
        assert "尚需确认实际退出" in page.locator("#content").inner_text()
        wait_status(lambda result: result.get("running") is False)
        cli = subprocess.run([sys.executable, "-m", "agent_workspace", "--home", str(app.home), "backend", "status"],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        reply = json.loads(cli.stdout)
        assert reply["ok"] is True
        exited = reply["result"]
        assert exited["running"] is False and exited["ready"] is False
        assert "已停止" not in page.locator("#content").inner_text()

        backend.start(app)
        wait_status(lambda result: result.get("ready") is True)
        page.get_by_role("button", name="重新连接", exact=True).click()
        page.wait_for_function("!document.getElementById('refresh').disabled")
        assert page.get_by_text("本机后台已就绪", exact=True).is_visible()
        assert "当前连接不可用" not in page.locator("#content").inner_text()
        assert "已重新连接" in page.locator("#content").inner_text()
        assert not app.registry.exists() and not failures
        assert "ISOLATED_BACKEND_BROWSER_MARKER" in backend.log(app)["content"]
        reconnected = backend.status(app)
        write_json(tmp_path / "backend-browser-observations.json", {
            "initial": {key: started[key] for key in ("pid", "ready", "running", "observed_at")},
            "restarted": {key: restarted[key] for key in ("pid", "ready", "running", "observed_at")},
            "cli_after_stop": {key: exited[key] for key in ("state", "ready", "running", "observed_at")},
            "reconnected": {key: reconnected[key] for key in ("pid", "ready", "running", "observed_at")},
        })
        page.screenshot(path=str(tmp_path / "backend-browser-reconnected.png"), full_page=True, animations="disabled")
    finally:
        try:
            context.close()
        finally:
            current = backend.status(app)
            if current.get("running"):
                backend.stop(app)
                wait_status(lambda result: result.get("running") is False)


@pytest.mark.parametrize("width", [390, 1440])
def test_worker_selection_shows_only_its_own_session(tmp_path, browser, width):
    from agent_workspace.app import App

    app = App(tmp_path / "worker-home")
    app.workspace_init("team", str(tmp_path / "team.git"), worker_support=True)
    app.create("team", "helper")
    app.worker_create("team", "helper", "日志调查", "独立检查构建日志", worker_id="logs")
    for worker_id in ("default", "logs"):
        binding = app.reserve("team", "helper", worker_id=worker_id)["binding"]
        app.bind("team", "helper", binding, "manual-worker-" + worker_id, worker_id=worker_id)
    server = make_server(app, 0, "worker-browser-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": width, "height": 960})
    page = context.new_page()
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/#token=worker-browser-token")
        page.wait_for_selector("#app:not(.hidden)")
        assert page.get_by_text("2 个 Worker", exact=True).is_visible()
        page.locator(".agent-name").click()
        assert page.locator("#worker-select").input_value() == "default"
        assert "manual-worker-default" in page.locator("#content").inner_text()
        assert "manual-worker-logs" not in page.locator("#content").inner_text()
        page.locator("#worker-select").select_option("logs")
        assert "manual-worker-logs" in page.locator("#content").inner_text()
        assert "manual-worker-default" not in page.locator("#content").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / f"worker-detail-{width}.png"), full_page=True, animations="disabled")
        assert not failures
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
