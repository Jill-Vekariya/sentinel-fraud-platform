# Azure deployment path

The working default is local Docker Compose. This repository also includes a **reference AKS manifest**, not a verified cloud deployment or Azure ML managed endpoint.

1. Create/select an Azure subscription, resource group, AKS cluster and Azure Container Registry using your company configuration.
2. Build and push the repository Dockerfile to your registry. Replace both `YOUR_REGISTRY/fraud-platform:1.0.0` references in `deploy/k8s/app.yaml`.
3. Provision a Kafka-compatible broker, create `transactions`, `decisions`, `transactions.dlq` topics with at least 3 partitions, and replace `YOUR_KAFKA:9092`. Key input by account ID. Configure TLS/SASL before using a managed external broker; the local worker currently assumes plaintext in a private demo network.
4. Create the `fraud-api-key` Kubernetes Secret with the `api-key` field. Use your secret manager; never commit credentials.
5. Apply the manifest: `kubectl apply -f deploy/k8s/app.yaml`. This uses a single API and sidecar worker with one PVC. The init container bootstraps a synthetic model on first deployment. For actual fraud data, replace bootstrap with a signed, validated artifact release.
6. Access locally: `kubectl port-forward service/fraud 8000:8000`.

Before any public exposure, add TLS ingress, identity-based authentication, network policy and audit/retention controls. Migrate SQLite to transactional Postgres and account state to a sharded design before increasing replicas. Azure ML can track training jobs/artifacts, but online serving here is AKS, not Azure ML. A managed Azure ML endpoint needs an explicit adapter and remote feature-state service. No cloud resources are created by this repository.
