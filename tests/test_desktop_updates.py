from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile

import pytest


def launcher():
    spec = importlib.util.spec_from_file_location("desktop_launcher", "desktop/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_keeps_credentials_but_removes_package_overrides():
    env = launcher().environment({
        "LINKEDIN_CLIENT_SECRET": "dummy-secret", "PATH": "/bin", "UV_CACHE_DIR": "/tmp/cache",
        "UV_INDEX": "https://attacker.invalid", "UV_OFFLINE": "1", "UV_OVERRIDE": "bad.txt",
        "UV_CONFIG_FILE": "bad.toml", "PYTHONPATH": "/evil", "PYTHONHOME": "/evil", "VIRTUAL_ENV": "/old",
    })
    assert env == {"LINKEDIN_CLIENT_SECRET": "dummy-secret", "PATH": "/bin", "UV_CACHE_DIR": "/tmp/cache"}


def _wheel(root: Path, version: str) -> Path:
    name = "flin_update_fixture"
    path = root / f"{name}-{version}-py3-none-any.whl"
    info = f"{name}-{version}.dist-info"
    files = {
        f"{name}.py": f'def main():\n    print("{version}")\n',
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: flin-update-fixture\nVersion: {version}\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/entry_points.txt": "[console_scripts]\nflin-update-fixture = flin_update_fixture:main\n",
    }
    files[f"{info}/RECORD"] = "".join(f"{file},,\n" for file in files) + f"{info}/RECORD,,\n"
    with zipfile.ZipFile(path, "w") as archive:
        for file, text in files.items():
            archive.writestr(file, text)
    return path


def test_same_launcher_and_cache_pick_up_new_release_without_reinstall(tmp_path):
    uv = shutil.which("uv")
    if not uv:
        pytest.fail("uv is required to verify real desktop updates")
    module = launcher()
    index = tmp_path / "simple" / "flin-update-fixture"
    index.mkdir(parents=True)
    first = _wheel(index, "1.0.0")
    page = index / "index.html"
    page.write_text(f'<a href="{first.name}">{first.name}</a>')
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    module.PYPI_INDEX = f"http://127.0.0.1:{server.server_port}/simple"
    module.SERVER_REQUIREMENT = "flin-update-fixture>=1.0.0"
    module.SERVER_COMMAND = "flin-update-fixture"
    env = module.environment(os.environ)
    env["UV_CACHE_DIR"] = str(tmp_path / "cache")
    args = module.command(uv)
    try:
        def run():
            return subprocess.run(args, env=env, capture_output=True, text=True, check=True, timeout=60).stdout.strip()
        assert run() == "1.0.0"
        second = _wheel(index, "1.0.1")
        preview = _wheel(index, "2.0.0rc1")
        page.write_text("\n".join(f'<a href="{p.name}">{p.name}</a>' for p in (first, second, preview)))
        assert run() == "1.0.1"
        assert args == module.command(uv)  # No launcher/config change between launches.
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_launcher_uses_claude_managed_uv_without_path_entry(monkeypatch):
    module = launcher()
    monkeypatch.setenv("UV", "/managed/uv")
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    calls = []
    monkeypatch.setattr(module.os, "execve", lambda *args: calls.append(args))
    module.main()
    assert calls[0][0] == "/managed/uv"
    assert calls[0][1] == module.command("/managed/uv")
