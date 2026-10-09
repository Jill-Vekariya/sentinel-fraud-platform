# Portfolio and interview preparation

## How to use this project on a resume

Use this as a project when you can run it, explain the design, reproduce the tests and discuss its limits. Describe your actual role in developing, adapting, validating and improving it. Tool assistance does not require branding in the project title; answer honestly if asked how you developed it. Do not claim independent authorship, production customers, business savings or features you did not implement.

Suggested project entry (adapt the verbs to your actual contribution):

**Sentinel — Streaming Fraud Decisioning** | Python, FastAPI, XGBoost, Isolation Forest, Kafka, Redis, Docker

- Developed and validated a fraud decisioning pipeline with account velocity features, model scoring, review rules and supervised SHAP explanations.
- Implemented idempotent scoring and an atomic SQL outbox with Kafka retries, reviewer feedback, drift monitoring and model rollback.
- Evaluated 2,400 synthetic chronological holdout transactions: PR-AUC 0.7426, recall 0.6203 and false-positive rate 0.6463%; verified the Docker pipeline with 100 streamed events.

Replace “Developed” or “Implemented” with “Adapted and tested” where that better describes your work. Do not list Kubernetes or Azure as deployment experience: their configuration is a reference only. Include the GitHub URL once publication succeeds. The current live demo is private, so do not promise recruiters unrestricted access.

## Build evidence of your own understanding

These are suggested exercises, not completed accomplishments. Record only work you actually perform, using normal dated commits:

1. Run the stack and score one normal transaction and one velocity burst. Explain the different decisions.
2. Replay an identical transaction and then change its amount with the same ID. Explain why the second operation conflicts.
3. Stop Redis and demonstrate that durable scoring still works. Explain why Redis is a mirror.
4. Add one useful change, such as a configurable review-capacity policy. Write a failing behavior check, implement it and document the tradeoff.
5. Compare classifier-only scoring against the 95/5 blend on identical validation/holdout splits. Discuss whether the anomaly component helps.
6. Record a short demonstration that explains a failure, recovery and measured result. Do not upload credentials or real transaction data.

## Four-week preparation plan

This is a practical study plan, not a hiring guarantee. Adjust it to the job description and recruiting guidance.

| Week | Practice | Evidence to produce |
|---|---|---|
| 1 | Python, arrays, hash maps, two pointers, binary search; explain rolling features | Solve problems unaided, state time/space complexity; demonstrate scoring |
| 2 | Trees, graphs, heaps, SQL joins/window functions; testing and failure recovery | Working solutions with edge cases; explain replay, outbox and DLQ |
| 3 | Classification metrics, leakage, calibration, drift; API/database design | Explain PR-AUC versus accuracy and threshold budgets; draw the architecture |
| 4 | Timed coding, system-design discussion and behavioral examples | Mock interviews; concise project walkthrough and real contribution stories |

For backend roles, emphasize coding, SQL, HTTP, transactions and distributed-system tradeoffs. For ML roles, add statistics, evaluation, feature leakage, imbalance, model deployment and monitoring. Prepare real examples of a difficult bug, a design decision, feedback you acted on and a change you personally delivered.

## Questions to answer without notes

- Where does each transaction become durable? What can still be duplicated?
- Why does temporal splitting matter? Which split chooses the threshold?
- What is the difference between a risk score and a calibrated probability?
- Why can review-only labels bias evaluation?
- What breaks with multiple API replicas? What would you change first?
- Which features exist in Docker but not in the hosted browser demo?
- What was your actual contribution, and what would you improve next?

## Official preparation references

Amazon's software development guidance includes programming, algorithms, data structures, databases and distributed computing, with coding assessments and design exercises: https://amazon.jobs/content/en/how-we-hire/interview-prep/software-development-topics

Microsoft's technical interview guidance covers problem solving, design, runnable code, testing, algorithms, data structures and role-specific ML topics: https://careers.microsoft.com/v2/global/en/hiring-tips/technical-interviewing

A strong project supports an application; it does not replace these skills or guarantee selection.
