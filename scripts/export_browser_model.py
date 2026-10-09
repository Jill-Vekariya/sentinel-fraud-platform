"""Export locally trained, trusted synthetic models for static browser inference."""
import json
from pathlib import Path
from fraud.model import ModelManager
from fraud.config import FEATURES

def main():
    manager = ModelManager().load()
    raw = json.loads((manager.directory / manager.version / "classifier.json").read_text())["learner"]
    if raw["gradient_booster"]["name"] != "gbtree":
        raise ValueError("Browser export supports only the project's gbtree classifier")
    forest = []
    for estimator in manager.anomaly.estimators_:
        tree = estimator.tree_
        forest.append({"left": tree.children_left.tolist(), "right": tree.children_right.tolist(),
                       "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(),
                       "count": tree.n_node_samples.tolist()})
    model = {"features": FEATURES, "base_score": float(raw["learner_model_param"]["base_score"]),
             "trees": raw["gradient_booster"]["model"]["trees"], "forest": forest,
             "max_samples": int(manager.anomaly.max_samples_), "reference": manager.meta["anomaly_reference"],
             "threshold": manager.meta["threshold"], "version": manager.version, "test": manager.meta["test"]}
    target = Path("hosted-demo/model.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(model, separators=(",", ":")))
    print(f"Exported {manager.version} to {target}")

if __name__ == "__main__":
    main()
