"""A configured completion-report capability over the existing platform commands."""
from pathlib import Path
import inspect

from .commands import execute
from .shared import material_path
from .util import Conflict, Error, read_json, slug


TOOLS = [
    {"name": "aw_report_completion",
     "description": "Send a completion report to the configured local recipient. Use one stable request_id. "
                    "If the result is unknown or the reply is lost, query aw_report_status with that ID; do not resend.",
     "inputSchema": {"type": "object", "properties": {
         "request_id": {"type": "string"}, "content": {"type": "string"}},
         "required": ["request_id", "content"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}},
    {"name": "aw_report_status",
     "description": "Read the original report publication without replaying it. not_recorded does not authorize a resend. Notification ACK is not business completion.",
     "inputSchema": {"type": "object", "properties": {"request_id": {"type": "string"}},
         "required": ["request_id"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True}},
    {"name": "aw_read_materials",
     "description": "Read only the shared material files selected in the local completion configuration.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True}},
]


class CompletionMCP:
    def __init__(self, app, path, actor=None, workspace=None):
        self.app, self.path = app, Path(path)
        self.config = self._read_config()
        self.actor = tuple(self.config[k] for k in ("workspace", "agent_id", "binding"))
        if actor is not None and actor != self.actor:
            raise Conflict("Completion configuration cannot replace the calling execution identity.")
        if workspace is not None and workspace != self.actor[0]:
            raise Conflict("Completion configuration differs from the selected Workspace.")

    def _read_config(self):
        value = read_json(self.path)
        fields = {"enabled", "workspace", "agent_id", "binding", "recipient", "material_paths"}
        if not isinstance(value, dict) or set(value) != fields:
            raise Error("Completion configuration requires enabled, workspace, agent_id, binding, recipient and material_paths.")
        if type(value["enabled"]) is not bool:
            raise Error("Completion enabled must be a boolean.")
        for name in ("workspace", "agent_id", "binding", "recipient"):
            if not isinstance(value[name], str):
                raise Error(f"Completion {name} must be an explicit local identifier.")
            slug(value[name])
        if not isinstance(value["material_paths"], list) or not value["material_paths"]:
            raise Error("Select the shared material files needed for this completion task.")
        for path in value["material_paths"]:
            material_path(path)
        return value

    def call(self, name, arguments):
        current = self._read_config()
        if not current["enabled"]:
            raise Conflict("This completion endpoint is disabled.")
        if any(current[k] != self.config[k] for k in current if k != "enabled"):
            raise Conflict("Completion scope changed; restart with the new configuration.")
        handlers = {"aw_report_completion": self._report, "aw_report_status": self._status,
                    "aw_read_materials": self._materials}
        if name not in handlers:
            raise Error("Unknown completion tool.")
        if not isinstance(arguments, dict):
            raise Error("Completion arguments must be a JSON object.")
        handler = handlers[name]
        try:
            inspect.signature(handler).bind(**arguments)
        except TypeError as exc:
            raise Error(f"Invalid arguments for {name}.") from exc
        return handler(**arguments)

    def _report(self, request_id, content):
        if not isinstance(request_id, str):
            raise Error("A completion report requires its stable request_id.")
        slug(request_id)
        return execute(self.app, "message.send", {"to": self.config["recipient"], "content": content,
                       "delivery": "normal", "request_id": request_id}, actor=self.actor)

    def _status(self, request_id):
        # A revoked Binding may inspect its own original receipt, but cannot write again.
        operation = execute(self.app, "message.operation", {"operation_id": request_id}, actor=self.actor)
        if operation["state"] == "not_recorded":
            return operation
        if (operation["type"] != "message" or operation["agent"] != self.actor[1]
                or operation["binding"] != self.actor[2]
                or operation["payload"]["to"]["agent"] != self.config["recipient"]
                or operation["payload"]["to"]["workspace"] != operation["payload"]["from"]["workspace"]):
            raise Conflict("This request does not belong to the configured completion scope.")
        if operation["state"] == "published":
            shared = execute(self.app, "message.show", {"message_id": request_id}, actor=self.actor)
            return {**operation, "notification_acknowledged": shared["ack"] is not None}
        return operation

    def _materials(self):
        self.app.require_binding(*self.actor)
        return execute(self.app, "workspace.read", {"paths": self.config["material_paths"]}, actor=self.actor)
