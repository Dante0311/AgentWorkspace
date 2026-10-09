"""Local project preferences, native ID discovery, and explicit sidebar preparation.

Project creation and folder editing remain manual; preparation never creates chats.
"""
from importlib.resources import files
from pathlib import Path
import json

from .util import Conflict, Error, Unavailable, Uncertain, digest, locked, now, read_json, slug, write_json


HARNESSES = ("codex", "claude", "workbuddy")


def _path(app, workspace, agent_id, harness):
    if harness not in HARNESSES:
        raise Error("Choose codex, claude or workbuddy for a desktop project reference.")
    root = app.root(workspace, agent_id)
    return root, root / ".aw-local/desktop-projects" / (harness + ".json")


def plan(app, workspace, agent_id, harness="codex"):
    root, path = _path(app, workspace, agent_id, harness)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        data = None
    value = json.loads(data) if data is not None else {}
    if not isinstance(value, dict):
        raise Error("Invalid desktop reference; preserve the file and inspect it before changing it.")
    project = {"project_name": f"AW · {workspace} · {agent_id}",
               "section_name": f"AW · {workspace}" if harness == "codex" else "",
               "product_paths": [], **value}
    if (not isinstance(project["product_paths"], list)
            or not all(isinstance(p, str) for p in project["product_paths"])):
        raise Error("Invalid product folder references; the original file was not changed.")
    return {"workspace": workspace, "agent_id": agent_id, "harness": harness,
            "primary_folder": str(root), "project": project,
            "revision": digest(data) if data is not None else None,
            "state": "manual_setup_required", "native_project_verified": False,
            "path_status": [{"path": p, "exists": Path(p).is_dir()} for p in project["product_paths"]],
            "instructions": (files("agent_workspace") / "resources/prompts/desktop-projects.md").read_text(encoding="utf-8")}


def save(app, workspace, agent_id, harness, project_name, section_name="", product_paths=None, revision=None):
    root, path = _path(app, workspace, agent_id, harness)
    for key, value in (("project_name", project_name), ("section_name", section_name)):
        if not isinstance(value, str) or len(value) > 160 or any(ord(c) < 32 for c in value):
            raise Error(f"Invalid {key}; use a short display name without control characters.")
    if not project_name.strip():
        raise Error("A project display name is required.")
    if section_name and harness != "codex":
        raise Error("Automatic/native sections are not verified for this desktop. Leave section_name empty.")
    if product_paths is None:
        product_paths = []
    if not isinstance(product_paths, list) or len(product_paths) > 20:
        raise Error("Select up to 20 explicit existing product folders.")
    paths = []
    for value in product_paths:
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
            raise Error("Use explicit folder paths, one per entry.")
        directory = Path(value).expanduser().resolve(strict=True)
        if not directory.is_dir() or directory == root:
            raise Error("A product folder must be an existing directory distinct from the Agent's primary folder.")
        if str(directory) not in paths:
            paths.append(str(directory))
    with locked(path.with_suffix(".lock")):
        actual = digest(path.read_bytes()) if path.exists() else None
        if revision != actual:
            raise Conflict("Desktop project preferences changed; read them again before saving.")
        previous = read_json(path, {})
        write_json(path, {**previous, "project_name": project_name, "section_name": section_name,
                          "product_paths": paths, "updated_at": now()})
    return {**plan(app, workspace, agent_id, harness), "saved": "local_reference_only",
            "native_project_changed": False, "binding_changed": False}


def _supports(adapter, name, arguments=()):
    # Enable only these narrow operations when the actual connection advertises
    # a matching schema. A tool name alone is not a verified invocation contract.
    schema = adapter.tool_schemas.get(name, {})
    if (name not in adapter.tools or schema.get('type') != 'object'
            or any(k in schema for k in ('$ref', 'oneOf', 'anyOf', 'allOf'))
            or not set(schema.get('required', [])).issubset(arguments)):
        return False
    properties = schema.get('properties', {})
    return all(properties.get(k, {}).get('type') == 'string' for k in arguments)


def _discover(adapter, root, preferred):
    if 'list_projects' not in adapter.tools:
        raise Unavailable('The captured connection cannot list local projects.')
    listed = adapter.call('list_projects', {})['projects']
    projects = [{k: p.get(k) for k in ('projectId', 'label', 'path')} for p in listed
                if p.get('projectKind') == 'local' and p.get('hostId') == 'local' and p.get('path')
                and Path(p['path']).resolve() == root.resolve()]
    matching = [p for p in projects if p['projectId'] == preferred] if preferred else projects
    selected = matching[0] if len(matching) == 1 else None
    capabilities = {'create_project': False, 'edit_folders': False,
                    'list_sections': _supports(adapter, 'list_sidebar_sections'),
                    'create_section': _supports(adapter, 'create_sidebar_section', ('name',)),
                    'move_project': _supports(adapter, 'move_project_to_sidebar_section', ('projectId', 'sectionId'))}
    sections, section_error = [], None
    if capabilities['list_sections']:
        try:
            sections = adapter.call('list_sidebar_sections', {})['sections']
            sections = [{k: section.get(k) for k in ('sectionId', 'name', 'itemKeys')} for section in sections]
        except (Error, OSError, ValueError, KeyError, TypeError):
            section_error = 'Native sidebar lookup failed; project selection remains available.'
            capabilities['list_sections'] = False
            sections = []
    return {'projects': projects, 'selected_project': selected, 'sections': sections,
            'capabilities': capabilities, 'native_project_verified': selected is not None,
            'state': ('ready' if selected else 'selection_required' if projects else 'manual_setup_required'),
            'section_state': 'lookup_failed' if section_error else 'available' if capabilities['list_sections'] else 'manual_setup_required',
            'section_error': section_error}


def discover(app, workspace, agent_id):
    from .runtime import Desktop
    result = plan(app, workspace, agent_id)
    root = app.root(workspace, agent_id)
    config = read_json(root / '.aw-local/runtime.json', {})
    if config.get('kind') != 'desktop' or not all(config.get(k) for k in ('command', 'pipe_path', 'caller_thread')):
        return {**result, 'state': 'connection_required', 'projects': [], 'sections': [],
                'capabilities': {}, 'native_project_verified': False}
    adapter = Desktop(root, config, None)
    try:
        native = _discover(adapter, root, config.get('project_id') or result['project'].get('native_project_id'))
    finally:
        adapter.close()
    return {**result, **native, 'binding_changed': False}


def prepare(app, workspace, agent_id, request_id, project_id=None, section_id=None,
            create_section=False, revision=None):
    """Adopt one verified project; optional sidebar work never creates a chat."""
    from .runtime import Desktop
    slug(request_id)
    if not isinstance(create_section, bool) or (create_section and section_id):
        raise Error('Choose an existing section or explicitly request a new one, not both.')
    root, preferences = _path(app, workspace, agent_id, 'codex')
    receipt = root / '.aw-local/desktop-preparations' / (request_id + '.json')
    fingerprint = {'project_id': project_id, 'section_id': section_id,
                   'create_section': create_section, 'revision': revision}
    # Serializes shared section names across this installation's Workspace members.
    folder = app.home / 'desktop-preparations' / slug(workspace)
    with locked(folder / 'prepare.lock'):
        previous = read_json(receipt)
        if previous:
            if previous['request'] != fingerprint:
                raise Conflict('Preparation request ID already has different arguments.')
            if previous['state'] == 'completed':
                return previous['result']
            raise Uncertain('Preparation was attempted; inspect its original result, do not repeat sidebar writes.')
        current = plan(app, workspace, agent_id)
        if current['revision'] != revision:
            raise Conflict('Desktop preferences changed; reread before adopting a project.')
        if app.agent(workspace, agent_id)['current']:
            raise Conflict('Handoff before changing the project of an active instance.')
        config_path = root / '.aw-local/runtime.json'
        original = config_path.read_bytes() if config_path.exists() else b'{}'
        config = json.loads(original)
        if config.get('kind') != 'desktop':
            raise Unavailable('Capture the real Codex Desktop connection first.')
        adapter = Desktop(root, config, None)
        try:
            preferred = project_id or config.get('project_id') or current['project'].get('native_project_id')
            native = _discover(adapter, root, preferred)
            selected = native['selected_project']
            if selected is None:
                return {**current, **native, 'saved': False, 'native_project_changed': False}
            if section_id and section_id not in {s['sectionId'] for s in native['sections']}:
                raise Error('Select a section returned by the captured native connection.')
            section_name = current['project']['section_name']
            if create_section and not section_name:
                raise Error('Save a nonempty proposed section name first, or skip sidebar preparation.')
            matches = ([s for s in native['sections'] if s['name'] == section_name]
                       if create_section and native['capabilities']['list_sections'] else [])
            if len(matches) > 1:
                raise Conflict('Several sections use that name; select the native ID explicitly.')
            intent = {'request': fingerprint, 'state': 'attempted', 'project_id': selected['projectId']}
            write_json(receipt, intent)
            chosen_section = section_id or (matches[0]['sectionId'] if matches else None)
            section_state = 'skipped' if not (section_id or create_section) else 'manual_setup_required'
            section_error = None
            try:
                if (create_section and chosen_section is None
                        and native['capabilities']['list_sections'] and native['capabilities']['create_section']):
                    section_receipt = folder / ('section-' + digest(section_name.encode()) + '.json')
                    if section_receipt.exists():
                        raise Uncertain('Section creation was already attempted; select the verified existing section instead.')
                    write_json(section_receipt, {'name': section_name, 'state': 'attempted'})
                    made = adapter.call('create_sidebar_section', {'name': section_name})
                    write_json(section_receipt, {'name': section_name, 'state': 'returned', 'result': made})
                    chosen_section = made.get('sectionId')
                    if not chosen_section:
                        raise Uncertain('Native section creation did not return its ID; do not create another.')
                membership = next((s for s in native['sections'] if s['sectionId'] == chosen_section), None)
                item_key = f"codex:project:{selected['projectId']}"
                if membership and item_key in (membership['itemKeys'] or []):
                    section_state = 'verified'
                elif chosen_section and native['capabilities']['move_project']:
                    adapter.call('move_project_to_sidebar_section', {'projectId': selected['projectId'], 'sectionId': chosen_section})
                    observed = _discover(adapter, root, selected['projectId'])
                    membership = next((s for s in observed['sections'] if s['sectionId'] == chosen_section), None)
                    if not membership or item_key not in (membership['itemKeys'] or []):
                        raise Uncertain('Sidebar write returned, but membership was not confirmed. Inspect, do not replay.')
                    section_state = 'verified'
            except (Error, OSError, ValueError, KeyError, TypeError) as exc:
                # Sidebar failure does not discard a verified project choice. Its
                # durable write intent still prevents blind section recreation.
                section_state = 'outcome_unknown'
                section_error = f'Sidebar preparation is unconfirmed ({type(exc).__name__}); inspect the original native result. Project reuse remains available.'
        finally:
            adapter.close()
        with locked(preferences.with_suffix('.lock')):
            if (config_path.read_bytes() != original or plan(app, workspace, agent_id)['revision'] != revision
                    or app.agent(workspace, agent_id)['current']):
                raise Conflict('Local configuration or execution entry changed; preserve the preparation receipt.')
            value = {**current['project'], 'native_project_id': selected['projectId'], 'updated_at': now()}
            if section_state == 'verified':
                value['native_section_id'] = chosen_section
            # Both stores retain the same native ID. A partial write is visible in the receipt.
            write_json(preferences, value)
            app.configure(workspace, agent_id, {**config, 'project_id': selected['projectId']})
        result = {**plan(app, workspace, agent_id), 'state': 'ready', 'native_project_verified': True,
                  'native_project_id': selected['projectId'], 'section_state': section_state, 'section_error': section_error,
                  'native_project_changed': False, 'binding_changed': False, 'session_created': False,
                  'product_folders_verified': False}
        write_json(receipt, {**intent, 'state': 'completed', 'result': result})
        return result
