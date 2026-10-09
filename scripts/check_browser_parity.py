"""Compare browser and Python inference on deterministic synthetic feature cases."""
import json, subprocess
from pathlib import Path
import numpy as np
from fraud.config import FEATURES
from fraud.model import ModelManager

def main():
    manager = ModelManager().load()
    exported = json.loads(Path("hosted-demo/model.json").read_text())
    if exported["version"] != manager.version:
        raise ValueError("Run python -m scripts.export_browser_model after model training")
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(200):
        hour = rng.uniform(0, 2*np.pi)
        values = [rng.uniform(0, 10), int(rng.integers(0, 25)), rng.uniform(0, 12),
                  rng.uniform(0, 30), int(rng.integers(0, 2)), int(rng.integers(0, 2)),
                  np.sin(hour), np.cos(hour)]
        rows.append(dict(zip(FEATURES, map(float, values))))
    code = """import fs from 'node:fs'; import {predict} from './hosted-demo/engine.js';
const input=JSON.parse(fs.readFileSync(0,'utf8')); console.log(JSON.stringify(input.rows.map(row=>predict(input.model,row))));"""
    result = subprocess.run(["node", "--input-type=module", "-e", code],
                            input=json.dumps({"model": exported, "rows": rows}), text=True,
                            capture_output=True, check=True)
    outputs = json.loads(result.stdout)
    delta = 0.0
    for features, browser in zip(rows, outputs):
        python = manager.score(features)
        for key in ["risk_score", "fraud_probability", "anomaly_percentile"]:
            delta = max(delta, abs(python[key]-browser[key]))
        if python["decision"] != browser["decision"]:
            raise AssertionError("Browser policy differs from Python")
    report = {"cases": len(rows), "max_score_difference": delta, "tolerance": 1e-5, "passed": delta <= 1e-5}
    Path("docs/browser-model-parity.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    if not report["passed"]:
        raise AssertionError("Browser scores outside tolerance")

if __name__ == "__main__":
    main()
