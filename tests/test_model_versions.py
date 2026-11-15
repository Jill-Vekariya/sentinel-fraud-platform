import json

import pytest

from fraud.model import ModelManager, point_to


INVALID_VERSIONS = [
    None,
    False,
    1,
    [],
    {},
    "",
    ".",
    "..",
    "../escape",
    "nested/model",
    "nested\\model",
    "/absolute",
    "C:\\models\\v1",
    "C:v1",
    "with space",
    "trailing.",
    "bad\x00name",
    "v" * 129,
]


@pytest.mark.parametrize("version", INVALID_VERSIONS)
def test_invalid_promotion_preserves_pointer(tmp_path, version):
    pointer = tmp_path / "current.json"
    pointer.write_text(json.dumps({"version": "stable", "previous": None}))
    previous = pointer.read_bytes()

    with pytest.raises(ValueError, match="invalid model version"):
        point_to(tmp_path, version)

    assert pointer.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("version", INVALID_VERSIONS)
def test_invalid_pointer_preserves_active_bundle(tmp_path, version):
    (tmp_path / "current.json").write_text(json.dumps({"version": version}))
    manager = ModelManager(tmp_path)
    manager.version = "stable"
    manager.clf, manager.anomaly, manager.meta = object(), object(), {"version": "stable"}
    previous = manager.clf, manager.anomaly, manager.meta

    with pytest.raises(ValueError, match="invalid model version"):
        manager.load()

    assert manager.version == "stable"
    assert manager.clf is previous[0]
    assert manager.anomaly is previous[1]
    assert manager.meta is previous[2]


@pytest.mark.parametrize("version", ["v1", "v1.2.3", "release-1_test", "v" * 128])
def test_supported_version_names_can_be_promoted(tmp_path, version):
    folder = tmp_path / version
    folder.mkdir()
    (folder / "metadata.json").write_text("{}")

    point_to(tmp_path, version)

    assert json.loads((tmp_path / "current.json").read_text())["version"] == version


@pytest.mark.parametrize("operation", ["promote", "load"])
def test_version_symlink_cannot_escape_model_directory(tmp_path, operation):
    root = tmp_path / "models"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "metadata.json").write_text("{}")
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable")

    with pytest.raises(ValueError, match="invalid model version"):
        if operation == "promote":
            point_to(root, "escape")
        else:
            (root / "current.json").write_text(json.dumps({"version": "escape"}))
            ModelManager(root).load()


def test_unknown_safe_version_does_not_create_pointer(tmp_path):
    with pytest.raises(ValueError, match="unknown model version"):
        point_to(tmp_path, "missing-v1")

    assert not (tmp_path / "current.json").exists()
    assert not list(tmp_path.glob("*.tmp"))
