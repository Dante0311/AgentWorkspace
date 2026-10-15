"""One instance-owned Codex choice, with a fixed snapshot per execution entry."""
from __future__ import annotations

import json
import re

from . import layout
from .util import Conflict, Error, digest, now, read_json, write_json


CODEX_KINDS = {"codex", "desktop"}
CHOICE_KEYS = {"model": "model", "effort": "effort", "model_reasoning_effort": "effort"}


def split_config(config):
    """Remove legacy model overrides while retaining executable/provider arguments."""
    local = dict(config)
    choice, origins = {}, {}

    def select(field, value, origin):
        if field in choice and choice[field] != value:
            raise Conflict(f"Conflicting Codex {field} choices in {origins[field]} and {origin}.")
        choice[field] = value
        origins[field] = origin

    for key, field in CHOICE_KEYS.items():
        if key in local:
            select(field, local.pop(key), key)
    args = local.get("command")
    if isinstance(args, list):
        kept, index = [], 0
        while index < len(args):
            arg = args[index]
            assignment = None
            count = 1
            if arg in ("-c", "--config") and index + 1 < len(args):
                assignment, count = args[index + 1], 2
            elif isinstance(arg, str) and (arg.startswith("--config=") or arg.startswith("-c=")):
                assignment = arg.split("=", 1)[1]
            if isinstance(assignment, str) and "=" in assignment:
                key, raw = assignment.split("=", 1)
                if key in ("model", "model_reasoning_effort"):
                    try:
                        value = json.loads(raw)
                    except ValueError:
                        # Native TOML accepts single-quoted literal strings too.
                        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
                            value = raw[1:-1]
                        else:
                            raise Error(f"Cannot migrate command override {key}; use an explicit string choice.")
                    select(CHOICE_KEYS[key], value, f"command:{key}")
                    index += count
                    continue
            if arg in ("--model", "-m") and index + 1 < len(args):
                select("model", args[index + 1], "command:--model")
                index += 2
                continue
            if isinstance(arg, str) and arg.startswith("--model="):
                select("model", arg.split("=", 1)[1], "command:--model")
                index += 1
                continue
            kept.extend(args[index:index + count])
            index += count
        local["command"] = kept
    return local, choice, origins


def validate(choice, *, source='Codex configuration'):
    if not isinstance(choice, dict):
        raise Error(f"{source} must be an object with explicit model and effort strings.")
    for field in ("model", "effort"):
        value = choice.get(field)
        pattern = r"[A-Za-z0-9_./:@+\[\]-]+" if field == "model" else r"[A-Za-z0-9_./:@+-]+"
        if not isinstance(value, str) or not value or not re.fullmatch(pattern, value):
            raise Error(f"{source}.{field} requires an explicit native identifier; no default is inherited.")
    return {field: choice[field] for field in ("model", "effort")}


def _document(root):
    path = layout.instance_path(root, 'config.json')
    document = read_json(path, {})
    if not isinstance(document, dict):
        raise Error(f"Instance {path.relative_to(root).as_posix()} must be an object.")
    return document


def desired(root):
    """Allow an incomplete saved choice to be inspected without starting anything."""
    return _document(root).get("codex")


def migrate(root):
    """Copy an old choice once. Subsequent local capture must not replace it."""
    with layout.lock(root, "files.lock"):
        path = layout.local_path(root, "runtime.json")
        config = read_json(path, {"kind": "manual"})
        if config.get("kind") not in CODEX_KINDS:
            return config
        local, choice, origins = split_config(config)
        document = _document(root)
        if choice:
            # Preserve even partial old choices. Launch validation names the missing field.
            source = {"path": path.relative_to(root).as_posix(), "sha256": digest(path.read_bytes()), "fields": origins,
                      "choice": choice}
            # Keep the old facts even if a subsequent explicit configure replaces
            # the desired section before its first checkpoint is published.
            history = read_json(layout.local_path(root, "model-migration.json"), [])
            if source not in history:
                write_json(layout.local_path(root, "model-migration.json"), [*history, source])
            if "codex" not in document:
                document["codex"] = {**choice, "migrated_from": source}
                write_json(layout.instance_path(root, 'config.json'), document)
            write_json(path, local)
        return local


def configure(root, config):
    migrate(root)
    local, choice, _ = split_config(config)
    with layout.lock(root, "files.lock"):
        if choice:
            document = _document(root)
            document["codex"] = choice
            write_json(layout.instance_path(root, 'config.json'), document)
        write_json(layout.local_path(root, "runtime.json"), local)


def selected(root):
    path = layout.instance_path(root, 'config.json')
    data = path.read_bytes() if path.exists() else b"{}"
    try:
        document = json.loads(data)
    except ValueError as exc:
        raise Error(f"Instance {path.relative_to(root).as_posix()} must contain valid JSON.") from exc
    if not isinstance(document, dict):
        raise Error(f"Instance {path.relative_to(root).as_posix()} must be an object.")
    choice = validate(document.get("codex"), source=f'{path.relative_to(root).as_posix()} codex')
    return {**choice, "source": {"path": path.relative_to(root).as_posix(), "section": "codex",
            "sha256": digest(data)}}


def adopted(root, binding=None, *, session=None):
    """An entry's snapshot wins over later changes to the desired asset."""
    record = read_json(layout.local_path(root, "entry.json"), {})
    if binding is not None and record.get("binding") not in (None, binding):
        raise Conflict("Model choice belongs to another execution entry.")
    saved = record.get("model_profile")
    if "model_profile" in record:
        validate(saved)
        return saved
    # A legacy entry retained its exact launch configuration. Never replace it with
    # an edited desired asset when resuming an already-existing native session.
    _, old_choice, _ = split_config(record.get("config", {}))
    if old_choice:
        choice = validate(old_choice)
        return {**choice, "source": {"path": layout.local_path(root, 'entry.json').relative_to(root).as_posix(), "section": "config",
                "sha256": digest((layout.local_path(root, "entry.json")).read_bytes())}}
    if session and record.get("binding"):
        raise Error(f"This native session has no saved adopted Codex choice; handoff before applying {layout.instance_path(root, 'config.json').relative_to(root).as_posix()}.")
    return selected(root)


def pin(root, binding, profile):
    with layout.lock(root, "profile.lock"):
        path = layout.local_path(root, "entry.json")
        record = read_json(path, {})
        if record.get("binding") != binding:
            raise Conflict("Cannot adopt a model choice for another execution entry.")
        if "model_profile" not in record:
            write_json(path, {**record, "model_profile": profile, "model_adopted_at": now()})
        return adopted(root, binding)


def check_catalog(profile, models, *, complete):
    matches = [item for item in models if profile["model"] in (item.get("model"), item.get("id"))]
    if not matches:
        if complete:
            raise Error("Selected Codex model is absent from this entry's reported model catalog; no fallback was used.")
        return {"catalog": "unconfirmed", "effective": "unconfirmed"}
    efforts = matches[0].get("supportedReasoningEfforts")
    if efforts is not None:
        supported = [item.get("reasoningEffort") if isinstance(item, dict) else item for item in efforts]
        if profile["effort"] not in supported:
            raise Error("Selected effort is unsupported for this Codex model; no fallback was used.")
    return {"catalog": "reported_by_current_entry", "effort": "reported" if efforts is not None else "unconfirmed",
            "effective": "unconfirmed"}


def receipt(profile, validation, *, accepted=None, result=None):
    report = result or {}
    model, effort = report.get("model"), report.get("reasoningEffort", report.get("thinking"))
    mismatch = ((model is not None and model != profile["model"])
                or (effort is not None and effort != profile["effort"]))
    effective = "unconfirmed"
    if mismatch:
        effective = "mismatch"
    elif model is not None and effort is not None:
        effective = "native_reported"
    return {"requested": profile, "validation": validation, "native_accepted": accepted,
            "effective": effective,
            "reported": {key: value for key, value in (("model", model), ("effort", effort)) if value is not None}}


def require_matching(receipt):
    if receipt["effective"] == "mismatch":
        raise Error("Native response reports a different model or effort; the requested configuration was not confirmed.")
