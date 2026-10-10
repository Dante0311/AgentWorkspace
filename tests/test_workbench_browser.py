"""Workbench 0.4 through real local HTTP and Chromium.

These checks keep the recovery and authority contracts while following the
0.4 information architecture. They use isolated Git data and no real model.
"""
import json
import os
import sys
import threading

import pytest

from agent_workspace import maintenance
from agent_workspace.messages import Messages
from agent_workspace.server import make_server
from agent_workspace.util import encode, read_json, write_json


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
    page.set_default_timeout(15000)
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page.goto(base + "/#token=browser-test-token")
        page.wait_for_selector("#app:not(.hidden)")
        yield app, bindings, page
        assert not failures, failures
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def nav(page, view):
    page.locator(f'[data-view="{view}"]').click()


def compose(page, content="original message"):
    nav(page, "collaboration")
    page.get_by_role("button", name="发送 Message", exact=True).click()
    page.get_by_label("发送实例", exact=True).select_option("alice")
    page.get_by_label("接收者（实例 ID 或 好友/实例）", exact=True).fill("bob")
    page.get_by_label("正文", exact=True).fill(content)


def pending(page):
    return page.evaluate("pendingMessage()")


@pytest.mark.parametrize("delivered", [False, True])
def test_message_response_loss_continues_only_original_request(ui, delivered):
    app, bindings, page = ui
    attempts = []

    def lose_response(route):
        body = route.request.post_data_json
        if body["command"] == "message.send":
            attempts.append(body["arguments"])
            if delivered:
                assert route.fetch().json()["ok"]
            route.abort()
        else:
            route.continue_()

    page.route("**/api/execute", lose_response)
    compose(page)
    page.locator("#form").evaluate("(form) => { form.requestSubmit(); form.requestSubmit(); }")
    page.wait_for_function("!busy && !!pendingMessage() && !!document.getElementById('error').textContent")
    assert len(attempts) == 1
    identifier = pending(page)["args"]["request_id"]
    assert attempts[0]["binding"] == bindings["alice"]
    assert len(Messages(app).list("sea")) == int(delivered)

    page.unroute("**/api/execute", lose_response)
    page.reload()
    page.wait_for_selector("#pending-operation:not(.hidden)")
    assert pending(page)["args"]["request_id"] == identifier
    assert len(Messages(app).list("sea")) == int(delivered)
    page.get_by_role("button", name="继续原请求", exact=True).click()
    page.wait_for_function("!busy && !pendingMessage()")
    result = Messages(app).list("sea")
    assert len(result) == 1 and result[0]["id"] == identifier
    assert Messages(app).show("sea", identifier)["message"]["content"] == "original message"


def test_message_storage_failure_prevents_network_send(ui):
    app, _, page = ui
    compose(page)
    page.evaluate("() => { Storage.prototype.setItem = function() { throw new Error('storage unavailable'); }; }")
    page.locator("#dialog-submit").click()
    page.wait_for_function("document.getElementById('error').textContent.includes('storage unavailable')")
    assert not Messages(app).list("sea")
    assert page.locator("#dialog").is_visible()


def test_create_agent_uses_selected_directory_and_shared_skill(ui, tmp_path):
    app, _, page = ui
    store = app.store("sea")
    store.change(
        "main",
        {
            "skills/review/SKILL.md": b"---\ndescription: Shared review\n---\nversion one",
            "skills/review/references/list.md": b"checklist",
        },
        {},
        "Add browser Skill",
    )
    page.locator("#refresh").click()
    page.get_by_role("button", name="创建 Agent", exact=True).click()
    page.get_by_label("名称", exact=True).fill("skill-user")
    page.get_by_label("实例 ID", exact=True).fill("skill-user")
    target = tmp_path / "separate-volume" / "skill-user"
    page.get_by_label("本机实例目录", exact=True).fill(str(target))
    page.get_by_label("运行入口", exact=True).select_option("manual")
    page.locator('fieldset[data-key="skills"] input[value="review"]').check()
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")

    root = app.root("sea", "skill-user")
    assert root == target.resolve()
    assert (root / ".agents/skills/review/references/list.md").read_bytes() == b"checklist"
    assert read_json(root / ".aw-local/runtime.json") == {"kind": "manual"}
    assert app.agent("sea", "skill-user")["current"] is None
    assert str(target.resolve()) in page.locator("#result-output").inner_text()

    responsibility = (root / "AGENTS.md").read_bytes()
    store.change("main", {"skills/review/SKILL.md": b"version two"}, {}, "Update browser Skill")
    page.locator("#refresh").click()
    card = page.locator("article.agent-row").filter(has_text="skill-user")
    card.locator(".agent-name").click()
    page.get_by_role("button", name="管理 Skill", exact=True).click()
    page.locator('fieldset[data-key="update"] input[value="review"]').check()
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    assert (root / ".agents/skills/review/SKILL.md").read_bytes() == b"version two"
    assert (root / "AGENTS.md").read_bytes() == responsibility


def test_caretaker_grants_are_explicit_and_revocable(ui):
    app, _, page = ui
    app.create("sea", "steward")
    store = app.store("sea")
    snap = store.snapshot()
    meta = snap.json("workspace.json")
    meta["caretakers"] = {"steward": "steward"}
    store.change("main", {"workspace.json": encode(meta)}, {"workspace.json": snap.entries["workspace.json"]}, "Test caretaker")
    page.locator("#refresh").click()
    nav(page, "caretakers")
    page.get_by_role("button", name="管家授权", exact=True).click()
    action = page.locator('fieldset[data-key="commands"] input[value="agent.start"]')
    target = page.locator('fieldset[data-key="targets"] input[value="alice"]')
    action.check()
    target.check()
    assert not page.locator('fieldset[data-key="targets"] input[value="*"]').is_checked()
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    grant = maintenance.status(app, "sea")["grants"]["steward"]
    assert grant["commands"] == ["agent.start"] and grant["targets"] == ["alice"]

    page.get_by_role("button", name="管家授权", exact=True).click()
    assert action.is_checked() and target.is_checked()
    action.uncheck()
    target.uncheck()
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    assert maintenance.status(app, "sea")["grants"]["steward"]["commands"] == []


def test_health_report_prefills_bounded_repair_and_rejects_changed_generation(ui):
    app, bindings, page = ui
    root = app.root("sea", "alice")
    config = root / ".aw-local/bridges/chat.json"
    status = root / ".aw-local/bridges/status/chat.json"
    write_json(config, {"enabled": True, "generation": "observed"})
    write_json(status, {"fatal": True})
    nav(page, "workspace")
    page.get_by_role("button", name="健康检查", exact=True).click()
    page.wait_for_function("document.getElementById('content').textContent.includes('bridge_fault')")
    page.get_by_role("button", name="处理", exact=True).click()
    assert page.locator("#f-agent_id").input_value() == "alice"
    assert page.locator("#f-expected_binding").input_value() == bindings["alice"]
    assert page.locator("#f-expected_generation").input_value() == "observed"

    write_json(config, {"enabled": True, "generation": "changed"})
    page.locator("#dialog-submit").click()
    page.wait_for_function("document.getElementById('dialog-description').textContent.includes('changed')")
    assert read_json(config)["generation"] == "changed"
    assert not list((maintenance.folder(app, "sea") / "repairs").glob("*.json"))


def test_damaged_observation_keeps_other_instances_and_diagnostics_usable(ui):
    app, bindings, page = ui
    damaged = app.root("sea", "alice") / ".aw-local/status.json"
    damaged.write_bytes(b"{broken")
    page.locator("#refresh").click()
    broken = page.locator("article.agent-row").filter(has_text="alice")
    broken.get_by_text("状态读取失败", exact=True).wait_for()
    assert broken.get_by_role("button", name="健康检查", exact=True).is_visible()
    assert not broken.get_by_role("button", name="进入新会话", exact=True).count()
    healthy = page.locator("article.agent-row").filter(has_text="bob")
    assert healthy.get_by_role("button", name="查看当前状态", exact=True).is_visible()

    broken.get_by_role("button", name="健康检查", exact=True).click()
    page.wait_for_function("document.getElementById('result-output').textContent.includes('local_observation_failed')")
    assert damaged.read_bytes() == b"{broken"
    assert app.agent("sea", "alice")["current"] == bindings["alice"]


def test_model_profile_requires_explicit_http_consent_and_resets_on_change(ui):
    app, _, page = ui
    app.create("sea", "http-profile")
    page.locator("#refresh").click()
    card = page.locator("article.agent-row").filter(has_text="http-profile")
    card.get_by_role("button", name="更多", exact=True).click()
    page.get_by_role("button", name="配置运行方式", exact=True).click()
    page.locator("#f-model").fill("gpt-test")
    page.locator("#f-effort").fill("low")
    page.locator("#f-executable").fill(sys.executable)
    url = page.locator("#f-base_url")
    consent = page.locator("#f-allow_http")
    url.fill("http://192.0.2.75:4000/v1")
    assert not consent.is_checked()
    page.locator("#dialog-submit").click()
    page.wait_for_function("document.getElementById('dialog-description').textContent.includes('allow-http')")
    path = app.root("sea", "http-profile") / ".aw-local/runtime.json"
    assert not path.exists()

    consent.check()
    url.fill("http://models.internal:4000/v1")
    assert not consent.is_checked()
    consent.check()
    page.locator("#f-kind").select_option("claude")
    assert not consent.is_checked()
    page.locator("#f-kind").select_option("codex")
    consent.check()
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    assert read_json(path)["allow_http"] is True
    assert app.agent("sea", "http-profile")["current"] is None


def test_desktop_project_form_preserves_local_reference_only(ui, tmp_path):
    from agent_workspace import desktop_projects

    app, _, page = ui
    product = tmp_path / "product"
    product.mkdir()
    before = app.store("sea").head("main")
    card = page.locator("article.agent-row").filter(has_text="alice")
    card.get_by_role("button", name="更多", exact=True).click()
    page.get_by_role("button", name="目录与桌面组织", exact=True).click()
    page.locator("#f-project_name").fill("My Existing Project")
    page.locator("#f-section_name").fill("My Existing Section")
    page.locator("#f-product_paths").fill(str(product))
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    value = desktop_projects.plan(app, "sea", "alice")
    assert value["project"]["project_name"] == "My Existing Project"
    assert value["project"]["section_name"] == "My Existing Section"
    assert value["native_project_verified"] is False
    assert app.store("sea").head("main") == before and not list(product.iterdir())

    page.get_by_role("button", name="目录与桌面组织", exact=True).click()
    assert page.locator("#f-project_name").input_value() == "My Existing Project"
    page.locator("#f-harness").select_option("workbuddy")
    page.wait_for_function("document.getElementById('f-section_name').disabled")
    assert page.locator("#f-section_name").input_value() == ""


def test_shared_material_read_uses_fixed_workspace_revision(ui):
    app, _, page = ui
    app.store("sea").change("main", {"knowledge/team.md": "共同约定：TEAM_BROWSER_MARKER".encode()}, {}, "Shared text")
    page.locator("#refresh").click()
    nav(page, "shared")
    page.get_by_role("button", name="读取指定共同资料", exact=True).click()
    page.get_by_label("路径，一行一个", exact=True).fill("knowledge/team.md")
    page.locator("#dialog-submit").click()
    page.wait_for_function("!document.getElementById('dialog').open && !busy")
    assert "TEAM_BROWSER_MARKER" in page.locator("#result-output").inner_text()
    last = page.evaluate("lastResult")
    assert last
    assert last["complete"] is True and last["files"][0]["content"] == "共同约定：TEAM_BROWSER_MARKER"


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 960}])
def test_workbench_forms_and_recovery_fit_viewport(ui, viewport):
    _, _, page = ui
    page.set_viewport_size(viewport)
    if viewport["width"] < 700:
        page.locator("#mobile-menu").click()
    page.get_by_role("button", name="创建 Agent", exact=True).click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#dialog").evaluate("d => d.scrollWidth <= d.clientWidth")
    page.locator("#dialog-cancel").click()
    if viewport["width"] < 700:
        page.locator("#mobile-menu").click()
    nav(page, "caretakers")
    page.get_by_role("button", name="限定维修", exact=True).click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#dialog").evaluate("d => d.scrollWidth <= d.clientWidth")


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
    page.set_default_timeout(20000)
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/setup#token=setup-browser-token")
        page.wait_for_selector("#app:not(.hidden)")
        page.locator("#name").fill("team")
        page.locator("#address").fill(str(repository))
        for role, directory in directories.items():
            page.locator(f"#dir-{role}").fill(str(directory))
        page.locator("#create").click()
        page.wait_for_function("document.getElementById('output').textContent.includes('\\\"state\\\": \\\"created\\\"')")
        for role, directory in directories.items():
            assert app.root("team", role) == directory.resolve()
            assert app.agent("team", role)["current"] is None
        assert page.locator("#workspace").input_value() == "team"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
