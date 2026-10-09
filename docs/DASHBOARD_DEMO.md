# Actual dashboard demonstration

[Watch or download sentinel-dashboard-demo.mp4](sentinel-dashboard-demo.mp4): 60 seconds, H.264, 1920 × 1080, on-screen captions, no audio. [Cover image](dashboard-demo-cover.jpg); [capture metadata and observed values](dashboard-demo-capture.json).

This video uses screenshots captured from the actual public Sentinel application after interacting with its controls. Captions and a frame were added outside the screenshots; the application content and displayed values were not replaced. It is a sequence of captured views rather than a continuous screen recording. The application source is `3aa476580805b547f0fba417cca3c88ed5e46906`; its [deployment](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/37956057385) and [CI](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/37955285101) passed.

| Time | Actual application action | Visible evidence |
|---|---|---|
| 0–8 s | Enter USD 45, US country, usual device on a new `walkthrough_20261009` account; evaluate risk | APPROVE, displayed risk 0.078, no prior events, amount ratio 0.45 |
| 8–18 s | Enter USD 6,000, GB country and a new device on the same account; evaluate risk | BLOCK, displayed risk 0.919, one prior five-minute event, clipped ratio 100, foreign-spike rule reason |
| 18–30 s | Scroll to classifier explanations | Native-equivalent Tree SHAP contributions in log-odds: amount +2.386, new device +2.240 and foreign flag +1.810; negative contributions also visible |
| 30–42 s | Inspect the separate real-data cost explorer at default assumptions | Five approaches; XGBoost threshold 0.03689, 87 flags, 30 false positives, 18 missed frauds, displayed cost EUR 2,640 |
| 42–52 s | Increase false-positive friction from EUR 5 to EUR 100 | Validation-selected threshold 0.62326, 45 flags, two false positives, 32 missed frauds, displayed cost EUR 4,026 |
| 52–60 s | Open “About this demo” | The application's own disclosure of browser inference/local history and the separate Docker backend |

The browser history also contains an earlier synthetic guided payment from the same verification session; the two manual walkthrough transactions share their own account. Amount inputs are USD for the synthetic scorer. Benchmark cost inputs are hypothetical EUR assumptions on the real dataset; those amounts and feature schemas must not be mixed. Displayed risk, contributions and costs are rounded to the UI precision.

The classifier explanation does not cover anomaly scoring or policy rules and is not causal. The cost explorer chooses thresholds using validation and shows holdout consequences; a change in a hypothetical cost assumption is not evidence of actual savings. The public application does not run the Python/Kafka backend.

The separate [48-second Docker API walkthrough](sentinel-demo.mp4) visualizes captured API requests/responses rather than dashboard footage. [Its provenance](DEMO_TRANSCRIPT.md) and the [full pipeline checklist](FINAL_CHECKLIST.md) provide supporting backend evidence.

Both videos are hosted in GitHub. No YouTube account or placeholder video link is required. For an interview, reproduce the interactions using [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) and explain the implementation with [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md).
