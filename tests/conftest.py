from pathlib import Path
import pytest
from agent_workspace.app import App

@pytest.fixture
def app(tmp_path):
    instance = App(tmp_path / 'home')
    instance.workspace_init('sea', str(tmp_path / 'sea.git'))
    return instance

@pytest.fixture
def pair(app):
    bindings = {}
    for name in ('alice', 'bob'):
        app.create('sea', name)
        bindings[name] = app.reserve('sea', name)['binding']
        app.bind('sea', name, bindings[name], 'native-' + name)
    return app, bindings
