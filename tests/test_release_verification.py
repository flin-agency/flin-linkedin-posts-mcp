"""Release verification must handle files produced by Trusted Publishing."""
import hashlib
import asyncio
import importlib.util
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def verifier(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("verify_pypi", "scripts/verify_pypi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    release = Path("dist/release")
    release.mkdir(parents=True)
    payload = {"urls": []}
    for suffix in ("-py3-none-any.whl", ".tar.gz"):
        name = "flin_linkedin_posts_mcp-1.2.3" + suffix
        data = name.encode()
        (release / name).write_bytes(data)
        (release / (name + ".publish.attestation")).write_text('{"attestation": true}')
        payload["urls"].append({"filename": name, "digests": {"sha256": hashlib.sha256(data).hexdigest()}})
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode()))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return module, payload, release


def test_published_distributions_verified_despite_attestation_sidecars(verifier, capsys):
    module, _, _ = verifier
    module.verify()
    assert "all distribution checksums verified" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["missing_published", "mismatched_hash", "missing_local"])
def test_both_distributions_are_required_and_hashes_must_match(verifier, failure):
    module, payload, release = verifier
    if failure == "missing_published":
        payload["urls"].pop()
    elif failure == "mismatched_hash":
        payload["urls"][0]["digests"]["sha256"] = "wrong"
    else:
        (release / payload["urls"][0]["filename"]).unlink()
    with pytest.raises((RuntimeError, FileNotFoundError)):
        module.verify()


@pytest.mark.parametrize("expected_version,failures,expected_calls", [
    ("1.2.3", 2, 3), ("1.2.3", 12, 12), (None, 1, 1),
])
def test_startup_retries_index_propagation_but_never_accepts_wrong_version(
    monkeypatch, expected_version, failures, expected_calls,
):
    spec = importlib.util.spec_from_file_location("smoke_mcpb", "scripts/smoke_mcpb.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    async def smoke(bundle, version):
        calls.append((bundle, version))
        if len(calls) <= failures:
            raise AssertionError("old version")

    async def sleep(_):
        pass

    monkeypatch.setattr(module, "smoke", smoke)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    if failures >= expected_calls:
        with pytest.raises(AssertionError, match="old version"):
            asyncio.run(module.verify_startup(Path("bundle.mcpb"), expected_version))
    else:
        asyncio.run(module.verify_startup(Path("bundle.mcpb"), expected_version))
    assert calls == [(Path("bundle.mcpb"), expected_version)] * expected_calls
