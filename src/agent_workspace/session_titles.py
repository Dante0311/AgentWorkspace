"""Requested Worker names and the title actually reported by a native session."""


def format_title(workspace_name, agent_name, worker_name):
    return f"{workspace_name} · {agent_name} · {worker_name}"


def receipt(requested, capability, *, accepted=None, reported=None):
    return {"requested": requested, "capability": capability, "native_accepted": accepted,
            "reported": reported,
            "effective": "unconfirmed" if reported is None else "native_reported" if reported == requested else "mismatch"}
