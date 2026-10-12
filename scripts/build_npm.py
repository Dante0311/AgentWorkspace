"""Pack the project wheel and a pinned Windows runtime into one npm artifact."""
from email.parser import BytesParser
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = "3.13.16"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
# Published at https://www.python.org/downloads/release/python-31316/.
PYTHON_SHA256 = "97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    directory = args.directory.resolve()
    wheels = sorted(directory.glob("git_native_agent_workspace-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected one project wheel in {directory}, found {len(wheels)}")
    wheel = wheels[0]
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise SystemExit("Node.js and npm are required to build the npm package.")

    cache = ROOT / ".cache" / "npm-build"
    cache.mkdir(parents=True, exist_ok=True)
    runtime_zip = cache / PYTHON_URL.rsplit("/", 1)[1]
    if not runtime_zip.exists():
        with urllib.request.urlopen(PYTHON_URL, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != PYTHON_SHA256:
            raise SystemExit("Downloaded Python runtime does not match its published SHA-256.")
        runtime_zip.write_bytes(payload)
    if sha256(runtime_zip) != PYTHON_SHA256:
        raise SystemExit(f"Cached Python runtime checksum mismatch: {runtime_zip}")

    # The staging directory is always created under this artifact directory.
    with tempfile.TemporaryDirectory(prefix="npm-build-", dir=directory) as temporary:
        package = Path(temporary)
        with ZipFile(wheel) as archive:
            metadata_name, = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            metadata = BytesParser().parsebytes(archive.read(metadata_name))
            archive.extractall(package / "app")
        version = metadata["Version"]
        match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?", version)
        if match is None:
            raise SystemExit(f"Unsupported project version for npm: {version}")
        npm_version = match[1]
        if match[2]:
            prerelease = {"a": "alpha", "b": "beta", "rc": "rc"}[match[2]]
            npm_version += f"-{prerelease}.{match[3]}"

        with ZipFile(runtime_zip) as archive:
            archive.extractall(package / "runtime")
        (package / "runtime" / "python313._pth").write_text(
            "python313.zip\n.\n../app\n", encoding="utf-8")
        manifest = json.loads((ROOT / "npm/package.json").read_text(encoding="utf-8"))
        manifest["version"] = npm_version
        (package / "package.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(ROOT / "npm/aw.cjs", package / "aw.cjs")
        shutil.copyfile(ROOT / "README.md", package / "README.md")
        (package / "build.json").write_text(json.dumps({
            "version": npm_version,
            "wheel": {"file": wheel.name, "sha256": sha256(wheel)},
            "python": {"version": PYTHON_VERSION, "url": PYTHON_URL, "sha256": PYTHON_SHA256},
        }, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run([npm, "pack", "--json", "--ignore-scripts", "--pack-destination", str(directory)],
                                cwd=package, text=True, encoding="utf-8", capture_output=True, check=True)
        packed, = json.loads(result.stdout)
    artifact = directory / packed["filename"]
    print(json.dumps({"file": str(artifact), "sha256": sha256(artifact),
                      "version": npm_version, "size": artifact.stat().st_size}))


if __name__ == "__main__":
    main()
