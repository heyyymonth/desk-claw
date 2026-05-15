# Deployment Storage Policy

This document defines how Desk AI selects Kubernetes storage for the current PVC-backed deployment. It covers the repo-supported release path; the actual StorageClass and snapshot class names are provider decisions.

## Current Persistent Volumes

| PVC | Required in mode | Contains | Backup policy |
| --- | --- | --- | --- |
| `backend-data` | Always, while SQLite is used | `deskclaw.db` with decisions, decision log, users, and redacted AI audit data. | SQLite online backup plus CSI snapshot when available. |
| `ollama-data` | In-cluster CPU/GPU Ollama only | Pulled `gemma4:latest` model cache. | Recreate by model pull, or snapshot when pull time/network constraints make that too slow. |

Both PVCs are `ReadWriteOnce`. The backend must remain at one replica while `DATABASE_URL` points at SQLite.

## StorageClass Decision

Choose a provider StorageClass before public cutover. The class should have:

- dynamic provisioning through the provider CSI driver;
- `ReadWriteOnce` support;
- `allowVolumeExpansion: true`;
- a reclaim/retention policy that matches the selected backup procedure;
- compatible `VolumeSnapshotClass` support if snapshots are part of the recovery plan.

Kubernetes uses the default StorageClass when a PVC has no `storageClassName`, which is fine for local defaults but too implicit for production. Production release manifests should pin the chosen class.

Render a release with one StorageClass for both PVCs:

```bash
STORAGE_CLASS_NAME=desk-ai-retain \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  PUBLIC_HOST=desk-ai.example.com \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

Use separate classes only when the provider decision intentionally separates SQLite storage from model-cache storage:

```bash
BACKEND_STORAGE_CLASS_NAME=desk-ai-db \
  OLLAMA_STORAGE_CLASS_NAME=desk-ai-model-cache \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

For external model mode, only `backend-data` is patched because `ollama-data` is removed:

```bash
K8S_BASE_DIR=infra/k8s-overlays/external-model \
  MODEL_ENDPOINT_URL=https://ollama.internal.example.com \
  STORAGE_CLASS_NAME=desk-ai-retain \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

## PVC Backup Annotations

The base PVCs include operational annotations so the storage policy is visible after apply:

| PVC | `desk.ai/storage-role` | `desk.ai/backup-policy` | `desk.ai/recovery-priority` |
| --- | --- | --- | --- |
| `backend-data` | `sqlite-state` | `sqlite-online-plus-csi-snapshot` | `critical` |
| `ollama-data` | `model-cache` | `recreate-or-csi-snapshot` | `rebuildable` |

These annotations are not a backup controller. They are repo-level guardrails for operators, audits, and validation scripts.

## Storage Verification

After applying a release, verify the selected class and PVC wiring:

```bash
VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots \
  REQUIRE_VOLUME_SNAPSHOT_CLASS=true \
  ./scripts/check-storage-policy.sh desk-ai-retain
```

For external model mode:

```bash
MODEL_HOSTING_MODE=external \
  VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots \
  REQUIRE_VOLUME_SNAPSHOT_CLASS=true \
  ./scripts/check-storage-policy.sh desk-ai-retain
```

The checker validates:

- StorageClass exists;
- StorageClass has a provisioner;
- `allowVolumeExpansion: true`, unless `REQUIRE_VOLUME_EXPANSION=false`;
- VolumeSnapshotClass exists when required;
- `backend-data` is bound to the selected StorageClass and has backup annotations;
- `ollama-data` is bound in in-cluster model modes and absent in external model mode.

## Snapshot Rendering

Use `scripts/render-volume-snapshot.sh` to create provider CSI snapshots when the selected cluster supports the snapshot CRDs and driver.

```bash
export SNAPSHOT_TS="$(date -u +%Y%m%dT%H%M%SZ)"

VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots \
  ./scripts/render-volume-snapshot.sh \
  backend-data \
  "backend-data-${SNAPSHOT_TS}" \
  "/tmp/backend-data-${SNAPSHOT_TS}.yaml"

kubectl apply -f "/tmp/backend-data-${SNAPSHOT_TS}.yaml"
```

For in-cluster Ollama:

```bash
VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots \
  ./scripts/render-volume-snapshot.sh \
  ollama-data \
  "ollama-data-${SNAPSHOT_TS}" \
  "/tmp/ollama-data-${SNAPSHOT_TS}.yaml"
```

`backend-data` snapshots do not replace SQLite online backups. Use both until managed Postgres replaces SQLite. `ollama-data` snapshots are optional when model pull time is acceptable.

## Production Gate

Do not accept public user data until:

- the production release manifest pins the chosen StorageClass;
- `scripts/check-storage-policy.sh` passes after rollout;
- the SQLite backup path in `docs/deployment-backup-restore.md` has been tested;
- at least one restore drill has completed in a non-production namespace or disposable cluster;
- snapshot support is proven if snapshots are part of the stated RTO.

## References

- [Kubernetes StorageClasses](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Kubernetes VolumeSnapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
