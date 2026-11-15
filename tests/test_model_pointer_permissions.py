import json
import os
import stat

import pytest

from fraud.model import point_to


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")


def bundle(root, version):
    folder = root / version
    folder.mkdir()
    (folder / "metadata.json").write_text("{}")


def test_first_pointer_is_readable_by_nonroot_runtime(tmp_path):
    bundle(tmp_path, "candidate")

    point_to(tmp_path, "candidate")

    pointer = tmp_path / "current.json"
    assert stat.S_IMODE(pointer.stat().st_mode) == 0o644
    assert json.loads(pointer.read_text())["version"] == "candidate"


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644])
def test_promotion_preserves_existing_pointer_permissions(tmp_path, mode):
    for version in ("stable", "candidate"):
        bundle(tmp_path, version)
    point_to(tmp_path, "stable")
    pointer = tmp_path / "current.json"
    pointer.chmod(mode)

    point_to(tmp_path, "candidate")

    assert stat.S_IMODE(pointer.stat().st_mode) == mode
    assert json.loads(pointer.read_text()) == {"version": "candidate", "previous": "stable"}
    assert not list(tmp_path.glob("*.tmp"))
