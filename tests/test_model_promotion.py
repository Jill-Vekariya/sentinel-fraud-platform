import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from fraud import model


def bundle(root, version):
    folder = root / version
    folder.mkdir()
    (folder / "metadata.json").write_text("{}")


def test_concurrent_promotions_use_independent_complete_files(tmp_path, monkeypatch):
    for version in ("stable", "one", "two"):
        bundle(tmp_path, version)
    model.point_to(tmp_path, "stable")
    barrier = Barrier(2)
    replace = model.os.replace
    observed = []

    def coordinated_replace(source, target):
        observed.append((str(source), json.loads(source.read_text())))
        barrier.wait(timeout=5)
        replace(source, target)

    monkeypatch.setattr(model.os, "replace", coordinated_replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(model.point_to, tmp_path, version) for version in ("one", "two")]
        for future in futures:
            future.result(timeout=10)

    assert len({path for path, _ in observed}) == 2
    assert {payload["version"] for _, payload in observed} == {"one", "two"}
    assert all(payload["previous"] == "stable" for _, payload in observed)
    assert json.loads((tmp_path / "current.json").read_text())["version"] in {"one", "two"}
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_replace_preserves_pointer_and_removes_temporary_file(tmp_path, monkeypatch):
    for version in ("stable", "candidate"):
        bundle(tmp_path, version)
    model.point_to(tmp_path, "stable")
    previous = (tmp_path / "current.json").read_bytes()

    def unavailable(source, target):
        raise OSError("replacement unavailable")

    monkeypatch.setattr(model.os, "replace", unavailable)
    with pytest.raises(OSError, match="replacement unavailable"):
        model.point_to(tmp_path, "candidate")

    assert (tmp_path / "current.json").read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_promotion_does_not_overwrite_an_unrelated_legacy_temp_file(tmp_path):
    bundle(tmp_path, "candidate")
    legacy = tmp_path / "pointer.tmp"
    legacy.write_text("owned by another operation")

    model.point_to(tmp_path, "candidate")

    assert legacy.read_text() == "owned by another operation"
    assert json.loads((tmp_path / "current.json").read_text()) == {
        "version": "candidate",
        "previous": None,
    }


def test_sequential_promotions_record_previous_version(tmp_path):
    for version in ("stable", "candidate"):
        bundle(tmp_path, version)
    model.point_to(tmp_path, "stable")
    model.point_to(tmp_path, "candidate")

    assert json.loads((tmp_path / "current.json").read_text()) == {
        "version": "candidate",
        "previous": "stable",
    }
    assert not list(tmp_path.glob("*.tmp"))
