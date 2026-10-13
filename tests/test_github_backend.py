"""REST protocol tests use in-memory Git objects, not a GitHub account."""
import base64
import hashlib
import json
from pathlib import Path
import pytest
from agent_workspace import app as app_module, layout
from agent_workspace.app import App
from agent_workspace.gitstore import GitHubStore
from agent_workspace.util import Conflict, encode


class MemoryGitHub:
    def __init__(self):
        self.refs,self.objects,self.calls={},{},[]
    def put(self,value):
        sha=hashlib.sha1(encode(value)).hexdigest();self.objects[sha]=value;return sha
    def request(self,method,path,value=None):
        self.calls.append((method,path))
        if method == 'PUT' and path.startswith('/contents/'):
            name = value['branch']
            parent = self.refs.get(name)
            tree = dict(self.objects[self.objects[parent]['tree']['sha']]) if parent else {}
            relative = path.removeprefix('/contents/')
            # Creating a file without its original SHA must never replace it.
            if relative in tree:
                raise Conflict('existing file requires its original SHA')
            assert 'sha' not in value
            tree[relative] = self.put({'content': value['content'], 'encoding': 'base64'})
            tree_sha = self.put(tree)
            commit = self.put({'message': value['message'], 'tree': {'sha': tree_sha},
                               'parents': [parent] if parent else []})
            self.refs[name] = commit
            return {'commit': {'sha': commit}, 'content': {'sha': tree[relative]}}
        if method=='GET' and path.startswith('/git/ref/heads/'):
            sha=self.refs.get(path.removeprefix('/git/ref/heads/'));return {'object':{'sha':sha}} if sha else None
        if method=='GET':
            sha=path.split('/')[-1].split('?')[0]
            obj=self.objects[sha]
            if path.startswith('/git/trees/'):
                if 'tree' in obj and isinstance(obj['tree'],dict):obj=self.objects[obj['tree']['sha']]
                return {'tree':[{'path':p,'mode':'100644','type':'blob','sha':s} for p,s in obj.items()], 'truncated':False}
            return obj
        if path=='/git/blobs':return {'sha':self.put(value)}
        if path=='/git/trees':
            tree=dict(self.objects.get(value.get('base_tree'),{}))
            for item in value['tree']:
                if item['sha'] is None:tree.pop(item['path'],None)
                else:tree[item['path']]=item['sha']
            return {'sha':self.put(tree)}
        if path=='/git/commits':
            return {'sha':self.put({**value,'tree':{'sha':value['tree']}})}
        if path=='/git/refs':
            name=value['ref'].removeprefix('refs/heads/')
            if name in self.refs:raise Conflict('existing ref')
            self.refs[name]=value['sha'];return {}
        if method=='PATCH':
            assert value['force'] is False
            name=path.removeprefix('/git/refs/heads/')
            if self.refs[name] not in self.objects[value['sha']]['parents']:raise Conflict('non fast-forward')
            self.refs[name]=value['sha'];return {}
        raise AssertionError((method,path))


def test_github_backend_no_clone_and_object_cas(tmp_path,monkeypatch):
    memory=MemoryGitHub();store=GitHubStore('github:owner/repo',tmp_path)
    monkeypatch.setattr(store,'request',memory.request)
    store.branch('main',{'workspace.json':b'{"name":"sea"}'})
    snap=store.snapshot();assert snap.bytes('workspace.json')==b'{"name":"sea"}'
    store.change('main',{'work/x.json':b'v1'},{'work/x.json':None},'new')
    old=store.snapshot()
    store.change('main',{'work/x.json':b'v2'},{'work/x.json':old.entries['work/x.json']},'update')
    with pytest.raises(Conflict):store.change('main',{'work/x.json':b'stale'},{'work/x.json':old.entries['work/x.json']},'stale')
    assert store.snapshot().bytes('work/x.json')==b'v2'
    assert not list(tmp_path.iterdir())


def test_empty_github_bootstrap_uses_contents(tmp_path, monkeypatch):
    memory = MemoryGitHub()
    store = GitHubStore('github:owner/repo', tmp_path)
    calls = []
    def request(method, path, value=None):
        calls.append((method, path, value))
        return memory.request(method, path, value)
    monkeypatch.setattr(store, 'request', request)
    metadata = {'name': 'sea'}
    store.bootstrap(metadata)
    method, path, body = calls[0]
    assert (method, path) == ('PUT', '/contents/workspace.json')
    assert 'sha' not in body and body['branch'] == 'main'
    assert json.loads(base64.b64decode(body['content'])) == metadata
    snap = store.snapshot()
    assert layout.version(snap, 'workspace') == 1
    assert snap.json('.agentworkspace/workspace.json') == metadata
    assert 'workspace.json' not in snap.entries
    # The second commit must preserve and consume the exact first Contents commit.
    parent = memory.objects[snap.revision]['parents'][0]
    initial = store.snapshot(revision=parent)
    assert initial.json('workspace.json') == metadata
    assert layout.MARKER not in initial.entries
    assert not list(tmp_path.iterdir())


def test_contents_bootstrap_does_not_replace_an_existing_workspace(tmp_path, monkeypatch):
    memory = MemoryGitHub()
    store = GitHubStore('github:owner/repo', tmp_path)
    monkeypatch.setattr(store, 'request', memory.request)
    original = {'workspace.json': encode({'name': 'existing'}), 'notes.md': b'Existing user work'}
    head = store.branch('main', original)
    with pytest.raises(Conflict):
        store.bootstrap({'name': 'replacement'})
    assert store.head('main') == head
    assert store.snapshot().all() == original


def test_remote_initialization_refuses_existing_current_layout_before_contents_put(tmp_path, monkeypatch):
    memory = MemoryGitHub()
    store = GitHubStore('github:owner/repo', tmp_path)
    monkeypatch.setattr(store, 'request', memory.request)
    store.bootstrap({'name': 'existing'})
    original = store.snapshot()
    memory.calls.clear()
    monkeypatch.setattr(app_module, 'open_store', lambda address, home: store)
    app = App(tmp_path / 'home')
    with pytest.raises(Conflict):
        app.workspace_bootstrap_remote('replacement', 'github:owner/repo')
    assert not any(method == 'PUT' for method, path in memory.calls)
    assert store.head('main') == original.revision
    assert store.snapshot().all() == original.all()
    assert app.workspace_list() == []
