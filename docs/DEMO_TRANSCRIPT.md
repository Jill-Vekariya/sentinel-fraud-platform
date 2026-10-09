# Recorded API demonstration

[Watch or download sentinel-demo.mp4](sentinel-demo.mp4): 48 seconds, H.264, 1280 × 720, with on-screen captions and no audio.

This is a captioned visualization of an actual Docker API session, rendered from its captured requests, responses and persisted feature values. It is not a dashboard screen recording. The source records are `recorded_demo` in [load-security.json](load-security.json); rerun `scripts.check_load_security` in an isolated API container to capture another session. Both events use a generated synthetic account and the active synthetic model.

| Time | Scene | Captured result or explanation |
|---|---|---|
| 0–6 s | Request and response overview | `POST /v1/score` returns a decision, ranking score and classifier contributions |
| 6–14 s | First payment | USD 45, US home/country, usual device; APPROVE, risk 0.078391 |
| 14–22 s | Foreign amount spike on the same account | USD 6,000, GB country/US home, new device; BLOCK, risk 0.918814; `FOREIGN_AMOUNT_SPIKE` reason |
| 22–33 s | Classifier explanation | Top positive native Tree SHAP contributions: amount, new device and foreign-country flag |
| 33–41 s | Measured checks | 300/300 successful load requests; 27 basic security checks; 20 concurrent retries stored one decision |
| 41–48 s | Scope and remaining limits | Separate browser demo/Docker backend, single writer, uncalibrated scores and hypothetical costs |

The amount-ratio feature uses a USD 100 reference mean before any history exists. The first event therefore has a ratio of 0.45. The next event uses recent account history and the ratio is clipped to the model's maximum of 100. Native Tree SHAP values describe supervised classifier log-odds; they do not explain the anomaly component or explicit review rules, establish causation, or turn the blended risk score into a calibrated probability.

For a live interview demonstration, follow [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) and explain the decisions in your own words. The video is supporting evidence, not a substitute for understanding the implementation.
