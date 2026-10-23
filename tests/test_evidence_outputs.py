"""An explicit output path must not destroy a retained benchmark."""

import pytest

from scripts.benchmark_real import run


def test_benchmark_refuses_existing_evidence_before_reading_dataset(tmp_path):
    output = tmp_path / "frozen.json"
    output.write_bytes(b"original measured evidence\n")
    with pytest.raises(FileExistsError, match="Choose a new output path"):
        run(tmp_path / "absent.csv", output)
    assert output.read_bytes() == b"original measured evidence\n"
