"""Check installed upstream SDK signatures without launching either Harness."""
from importlib import import_module, metadata
import inspect
from pathlib import Path
import sys
import tempfile


async def hook(data, tool_use_id, context):
    return {}


async def permission(tool, arguments, context):
    raise AssertionError("A signature check must never invoke a model or a tool.")


def main():
    with tempfile.TemporaryDirectory(prefix="aw-sdk-contract-") as temporary:
        for package, module, client_name, options_name, cli_key in (
            ("claude-agent-sdk", "claude_agent_sdk", "ClaudeSDKClient", "ClaudeAgentOptions", "cli_path"),
            ("codebuddy-agent-sdk", "codebuddy_agent_sdk", "CodeBuddySDKClient", "CodeBuddyAgentOptions", "codebuddy_code_path"),
        ):
            sdk=import_module(module)
            options=getattr(sdk,options_name)(
                cwd=temporary, env={"AW_BINDING":"contract"}, permission_mode="default", setting_sources=[],
                mcp_servers={"aw":{"type":"stdio","command":sys.executable,"args":["--version"]}},
                hooks={"PreToolUse":[sdk.HookMatcher(hooks=[hook])]}, can_use_tool=permission,
                include_partial_messages=True, model="contract-only", effort="high", **{cli_key:sys.executable})
            assert options.setting_sources == [] and options.env["AW_BINDING"] == "contract"
            client=getattr(sdk,client_name)
            for method in ("connect","query","receive_messages","disconnect"):
                assert callable(getattr(client,method,None)), (module,method)
            assert "prompt" in inspect.signature(client.query).parameters
            sdk.PermissionResultAllow(updated_input={})
            sdk.PermissionResultDeny(message="contract")
            print(f"PASS: {package} {metadata.version(package)} public options and streaming methods; no session started")


if __name__ == "__main__": main()
