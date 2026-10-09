# Browser demo

Static XGBoost + Isolation Forest inference, synthetic inputs, browser-local history and feedback. No server API, Kafka, Redis, shared ledger, SHAP or retraining runs here. Do not enter real personal or financial data. The exported model is trained on synthetic events.

The previous hosted demo remains private. Its workspace-hosted URL has been removed from this personal repository. Personal hosting is pending a visibility decision. GitHub source visibility does not change an existing live demo's access policy.

Project contact: jillvekariya.10@gmail.com.

After training the Python model, regenerate this export with `python -m scripts.export_browser_model`. Run `python -m scripts.check_browser_parity` from the repository root (Python dependencies and Node required). To inspect locally, serve this directory using any static web server; it must support JavaScript modules. Static hosts can publish this directory without the Docker backend.
