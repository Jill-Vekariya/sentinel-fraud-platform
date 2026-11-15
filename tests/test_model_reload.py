import hashlib
import json
import pickle

import pytest

from fraud import model


class ClassifierStub:
    def load_model(self, path):
        self.version = path.read_text()
        if self.version == "invalid-classifier":
            raise ValueError("classifier rejected")


@pytest.fixture(autouse=True)
def classifier_stub(monkeypatch):
    monkeypatch.setattr(model.xgb, "XGBClassifier", ClassifierStub)


def write_bundle(root, version, failure=None):
    folder = root / version
    folder.mkdir(exist_ok=True)
    classifier = b"invalid-classifier" if failure == "classifier" else version.encode()
    anomaly = b"not-a-pickle" if failure == "anomaly" else pickle.dumps({"version": version})
    meta = {
        "version": version,
        "classifier_sha256": hashlib.sha256(classifier).hexdigest(),
        "anomaly_sha256": hashlib.sha256(anomaly).hexdigest(),
    }
    (folder / "classifier.json").write_bytes(classifier)
    (folder / "anomaly.pkl").write_bytes(anomaly)
    (folder / "metadata.json").write_text(json.dumps(meta))


def load_stable(root):
    write_bundle(root, "stable")
    model.point_to(root, "stable")
    return model.ModelManager(root).load()


def snapshot(manager):
    return manager.clf, manager.anomaly, manager.meta, manager.version


def assert_unchanged(manager, previous):
    assert manager.clf is previous[0]
    assert manager.anomaly is previous[1]
    assert manager.meta is previous[2]
    assert manager.version == previous[3]


@pytest.mark.parametrize("failure", ["classifier", "anomaly"])
def test_failed_reload_preserves_complete_active_bundle(tmp_path, failure):
    manager = load_stable(tmp_path)
    previous = snapshot(manager)
    write_bundle(tmp_path, "candidate", failure)
    model.point_to(tmp_path, "candidate")

    with pytest.raises((ValueError, pickle.UnpicklingError)):
        manager.load()

    assert_unchanged(manager, previous)


@pytest.mark.parametrize("artifact", ["classifier.json", "anomaly.pkl"])
def test_checksum_failure_preserves_complete_active_bundle(tmp_path, artifact):
    manager = load_stable(tmp_path)
    previous = snapshot(manager)
    write_bundle(tmp_path, "candidate")
    (tmp_path / "candidate" / artifact).write_bytes(b"tampered")
    model.point_to(tmp_path, "candidate")

    with pytest.raises(ValueError, match="checksum"):
        manager.load()

    assert_unchanged(manager, previous)


def test_failed_initial_load_does_not_publish_partial_bundle(tmp_path):
    write_bundle(tmp_path, "candidate", "anomaly")
    model.point_to(tmp_path, "candidate")
    manager = model.ModelManager(tmp_path)

    with pytest.raises(pickle.UnpicklingError):
        manager.load()

    assert manager.version is None
    assert not any(hasattr(manager, name) for name in ("clf", "anomaly", "meta"))


def test_successful_reload_publishes_candidate_and_same_version_is_noop(tmp_path):
    manager = load_stable(tmp_path)
    previous = snapshot(manager)
    write_bundle(tmp_path, "candidate")
    model.point_to(tmp_path, "candidate")

    assert manager.load() is manager
    assert manager.clf is not previous[0]
    assert manager.clf.version == "candidate"
    assert manager.anomaly == {"version": "candidate"}
    assert manager.meta["version"] == manager.version == "candidate"
    active = snapshot(manager)
    assert manager.load() is manager
    assert_unchanged(manager, active)


def test_repaired_candidate_can_be_loaded_after_failure(tmp_path):
    manager = load_stable(tmp_path)
    write_bundle(tmp_path, "candidate", "anomaly")
    model.point_to(tmp_path, "candidate")

    with pytest.raises(pickle.UnpicklingError):
        manager.load()

    write_bundle(tmp_path, "candidate")
    manager.load()
    assert manager.clf.version == manager.version == "candidate"
    assert manager.anomaly == {"version": "candidate"}
    assert manager.meta["version"] == "candidate"
