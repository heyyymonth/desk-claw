# Deployment Backup And Restore

This runbook covers the current PVC-backed deployment until managed Postgres and provider-managed storage replace the local durable state.

## Current Persistent State

| PVC | Mount | Contains | Criticality |
| --- | --- | --- | --- |
| `backend-data` | `/app/data` in the backend pod | `deskclaw.db`, including decisions, workflow decision log, app users, and redacted AI audit/telemetry source rows. | Critical. Back up before deploys, migrations, and on a regular schedule. |
| `ollama-data` | `/root/.ollama` in the Ollama pod | Pulled local model artifacts, currently `gemma4:latest`. | Recreatable if Ollama registry access is available. Snapshot when pull time, network policy, or air-gapped operation makes redownload risky. |

The backend can run on SQLite or managed Postgres. Keep backend replicas at one while `DATABASE_URL` points at SQLite; use the managed Postgres backup/PITR plan after `DATABASE_MODE=postgres` cutover.

## Backup Objectives

Use these as starting points until product usage and hosting provider are known:

| State | RPO target | RTO target | Backup method |
| --- | --- | --- | --- |
| `backend-data` SQLite | 24 hours for private pilot, plus a backup before each release or migration. | Under 30 minutes for restore from a local/off-cluster backup. | SQLite online backup plus optional provider volume snapshot. |
| `ollama-data` model cache | After every model change, or weekly if model pulls are slow. | Under model download time, or under 30 minutes if restoring from a snapshot. | Prefer re-pull; use provider volume snapshots when redownload is too slow or blocked. |

Store backups off-cluster and encrypted. Do not commit database backups, snapshots, exported tables, or model artifacts.

## Backend SQLite Backup

This path does not require the `sqlite3` CLI inside the container. It uses Python's SQLite backup API from the running backend pod, then streams the backup file to the operator machine.

```bash
export NS=desk-ai
export BACKUP_DIR="./backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

export BACKEND_POD="$(kubectl -n "$NS" get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')"

kubectl -n "$NS" exec "$BACKEND_POD" -- python -c '
import sqlite3
src = sqlite3.connect("/app/data/deskclaw.db")
dst = sqlite3.connect("/tmp/deskclaw-backup.db")
src.backup(dst)
dst.close()
src.close()
'

kubectl -n "$NS" exec "$BACKEND_POD" -- python -c '
import sqlite3
result = sqlite3.connect("/tmp/deskclaw-backup.db").execute("PRAGMA integrity_check").fetchone()[0]
print(result)
raise SystemExit(0 if result == "ok" else 1)
'

kubectl -n "$NS" exec "$BACKEND_POD" -- cat /tmp/deskclaw-backup.db > "$BACKUP_DIR/deskclaw.db"
gzip -9 "$BACKUP_DIR/deskclaw.db"
```

Record the release tag and row counts with the backup:

```bash
kubectl -n "$NS" get deployment backend -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}' > "$BACKUP_DIR/backend-image.txt"

python3 - "$BACKUP_DIR/deskclaw.db.gz" > "$BACKUP_DIR/sqlite-row-counts.txt" <<'PY'
import gzip
import shutil
import sqlite3
import sys
import tempfile

source = sys.argv[1]
with tempfile.NamedTemporaryFile() as tmp:
    with gzip.open(source, "rb") as gz:
        shutil.copyfileobj(gz, tmp)
    tmp.flush()
    con = sqlite3.connect(tmp.name)
    for table in ("decisions", "app_users", "ai_audit_log", "decision_log"):
        count = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"{table}={count}")
PY
```

Move `$BACKUP_DIR` to encrypted off-cluster storage after it is created.

## Backend SQLite Restore

Use this when restoring the current SQLite-backed deployment. If a Postgres canary has already accepted writes, follow `docs/deployment-database-migration.md` instead because rollback then becomes a data reconciliation problem.

1. Freeze public traffic.

   Put the site in maintenance mode, remove the ingress route, or otherwise block user writes.

2. Stop frontend and backend pods.

   ```bash
   export NS=desk-ai
   kubectl -n "$NS" scale deployment/frontend --replicas=0
   kubectl -n "$NS" scale deployment/backend --replicas=0
   ```

3. Start a temporary restore pod that mounts `backend-data`.

   ```bash
   cat <<'YAML' | kubectl apply -f -
   apiVersion: v1
   kind: Pod
   metadata:
     name: backend-data-restore
     namespace: desk-ai
   spec:
     restartPolicy: Never
     containers:
       - name: restore
         image: python:3.11-slim
         command: ["sleep", "3600"]
         volumeMounts:
           - name: backend-data
             mountPath: /app/data
     volumes:
       - name: backend-data
         persistentVolumeClaim:
           claimName: backend-data
   YAML

   kubectl -n "$NS" wait --for=condition=Ready pod/backend-data-restore --timeout=120s
   ```

4. Restore the database file and verify integrity.

   ```bash
   gunzip -c ./deskclaw.db.gz | kubectl -n "$NS" exec -i backend-data-restore -- sh -c 'cat > /app/data/deskclaw.db'

   kubectl -n "$NS" exec backend-data-restore -- python -c '
import sqlite3
result = sqlite3.connect("/app/data/deskclaw.db").execute("PRAGMA integrity_check").fetchone()[0]
print(result)
raise SystemExit(0 if result == "ok" else 1)
'
   ```

5. Remove the restore pod and restart the app.

   ```bash
   kubectl -n "$NS" delete pod backend-data-restore
   kubectl -n "$NS" scale deployment/backend --replicas=1
   kubectl -n "$NS" rollout status deployment/backend --timeout=600s
   kubectl -n "$NS" scale deployment/frontend --replicas=2
   kubectl -n "$NS" rollout status deployment/frontend --timeout=300s
   ./scripts/smoke-deploy.sh https://desk-ai.example.com
   ```

6. Validate application data.

   Check admin telemetry, decision logs, and row counts against the backup metadata before reopening public traffic.

## Provider Volume Snapshots

If the selected cluster supports CSI `VolumeSnapshot`, use provider-native snapshots in addition to the SQLite backup. This is especially useful for `ollama-data`. StorageClass and VolumeSnapshotClass selection is covered in `docs/deployment-storage-policy.md`.

Render a backend data snapshot:

```bash
export SNAPSHOT_TS="$(date -u +%Y%m%dT%H%M%SZ)"

VOLUME_SNAPSHOT_CLASS_NAME=desk-ai-snapshots \
  ./scripts/render-volume-snapshot.sh \
  backend-data \
  "backend-data-${SNAPSHOT_TS}" \
  "/tmp/backend-data-${SNAPSHOT_TS}.yaml"

kubectl apply -f "/tmp/backend-data-${SNAPSHOT_TS}.yaml"
```

Restore shape:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: backend-data
  namespace: desk-ai
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  dataSource:
    name: backend-data-20260515
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

Do a restore drill in a non-production namespace before relying on snapshots for production recovery.

## Ollama Data Recovery

The preferred recovery path for `ollama-data` is to recreate the PVC and re-run the model pull job:

```bash
kubectl -n desk-ai scale deployment/backend --replicas=0
kubectl -n desk-ai delete job ollama-pull-gemma4 --ignore-not-found
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai rollout status deployment/ollama --timeout=300s
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
kubectl -n desk-ai scale deployment/backend --replicas=1
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
```

Use a volume snapshot for `ollama-data` when:

- model pulls regularly exceed the required recovery window;
- egress to the model registry is restricted;
- the deployment is in an air-gapped environment;
- the model cache includes manually loaded artifacts that cannot be recreated from the registry.

## Restore Drills

Run a restore drill before public cutover and after any storage-class change:

1. Create a backup from the current pilot environment.
2. Restore it into a separate namespace or disposable cluster.
3. Deploy the same immutable `git-<sha>` image tag.
4. Run `./scripts/smoke-deploy.sh`.
5. Verify row counts, admin telemetry, and decision logs.
6. Record the elapsed restore time and any manual steps.

## Guardrails

- Do not rely on PVCs as backups. PVCs are live disks, not recovery copies.
- Do not store backups only inside the same cluster.
- Do not restore SQLite while backend pods are running.
- Do not scale backend above one replica while SQLite is in use.
- Do not delete old SQLite backups until managed Postgres backup and point-in-time recovery are proven.
- Do not assume provider snapshots are portable across regions or hyperscalers.
