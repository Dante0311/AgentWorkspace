"""Public asset and ordinary-session boundaries retain their meaning in both layouts."""
import sys
from types import SimpleNamespace

import pytest

from agent_workspace import layout, sessions
from agent_workspace.app import App
from agent_workspace.commands import assets
from agent_workspace.util import Conflict, Error, write_bytes


@pytest.mark.parametrize('path', [
    '.agentworkspace/identity.json', '.agentworkspace/layout.json',
    '.agentworkspace/local/operations/software-update.json', '.aw-local/control.json',
])
def test_asset_write_cannot_change_platform_metadata(tmp_path, path):
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    app = SimpleNamespace(root=lambda *args: tmp_path)
    before = (tmp_path / layout.MARKER).read_bytes()
    with pytest.raises(Error):
        assets(app, 'write', 'sea', 'alice', path, '{}')
    assert (tmp_path / layout.MARKER).read_bytes() == before
    if path != layout.MARKER:
        assert not (tmp_path / path).exists()


@pytest.mark.parametrize('path', ['notes/work.md', '.agentworkspace/config.json',
                                  '.agentworkspace/messages/processing.md'])
def test_user_assets_and_saved_configuration_remain_editable(tmp_path, path):
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    app = SimpleNamespace(root=lambda *args: tmp_path)
    result = assets(app, 'write', 'sea', 'alice', path, 'first')
    readback = assets(app, 'read', 'sea', 'alice', path)
    assert readback['content'] == 'first' and readback['revision'] == result['revision']
    assets(app, 'write', 'sea', 'alice', path, 'second', revision=readback['revision'])
    assert (tmp_path / path).read_text() == 'second'


def test_new_instance_and_its_children_cannot_be_used_as_ordinary_sessions(tmp_path):
    app = App(tmp_path / 'home')
    root = tmp_path / 'instance'
    write_bytes(root / layout.MARKER, layout.marker('instance'))
    child = root / 'notes'
    child.mkdir()
    for directory in (root, child):
        with pytest.raises(Conflict, match='Agent instance'):
            sessions.prepare(app, 'codex', str(directory), executable=sys.executable)


def test_shared_workspace_is_still_usable_as_an_ordinary_work_directory(tmp_path):
    app = App(tmp_path / 'home')
    root = tmp_path / 'shared-project'
    write_bytes(root / layout.MARKER, layout.marker('workspace'))
    result = sessions.prepare(app, 'codex', str(root), executable=sys.executable)
    assert result['state'] == 'prepared' and result['native_session'] == 'not_observed'
