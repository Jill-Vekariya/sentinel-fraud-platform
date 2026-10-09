# Personal browser demo

Hosted under the Jill GitHub account, with project contact jillvekariya.10@gmail.com. The public static demo runs the synthetic classifier and anomaly model, exact cover-based classifier Tree SHAP, guided scenarios, local feedback/history, and a cost explorer based on recorded real-data benchmark results.

The real ULB/Worldline benchmark uses anonymized PCA features, so its models are separate from the synthetic live transaction schema. Financial outcomes use explicit hypothetical cost assumptions. The browser chooses scenario thresholds using validation aggregates and displays holdout outcomes. It does not run the Python API, Kafka, Redis, a server ledger or retraining.

After training: `python -m scripts.export_browser_model`, `python -m scripts.check_browser_parity`, `python -m scripts.check_browser_explanations`. Run `npm install` and `npm run test:hosted` to verify interactions. The publish workflow packages only this directory for GitHub Pages. No raw real dataset is published.
