#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: render-volume-snapshot.sh <pvc-name> <snapshot-name> [output-file]

Renders a snapshot.storage.k8s.io/v1 VolumeSnapshot for a Desk AI PVC.

Environment:
  NAMESPACE=desk-ai
  VOLUME_SNAPSHOT_CLASS_NAME=<provider-snapshot-class>
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage
  exit 1
fi

PVC_NAME="$1"
SNAPSHOT_NAME="$2"
OUTPUT_FILE="${3:-}"
NAMESPACE="${NAMESPACE:-desk-ai}"
VOLUME_SNAPSHOT_CLASS_NAME="${VOLUME_SNAPSHOT_CLASS_NAME:-}"

validate_name() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]; then
    echo "$label must be a valid Kubernetes DNS subdomain name." >&2
    exit 1
  fi
}

case "$PVC_NAME" in
  backend-data | ollama-data) ;;
  *)
    echo "pvc-name must be backend-data or ollama-data." >&2
    exit 1
    ;;
esac

validate_name "$SNAPSHOT_NAME" "snapshot-name"
validate_name "$NAMESPACE" "NAMESPACE"

if [[ -z "$VOLUME_SNAPSHOT_CLASS_NAME" ]]; then
  echo "VOLUME_SNAPSHOT_CLASS_NAME must be set." >&2
  exit 1
fi
validate_name "$VOLUME_SNAPSHOT_CLASS_NAME" "VOLUME_SNAPSHOT_CLASS_NAME"

render() {
  cat <<YAML
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: $SNAPSHOT_NAME
  namespace: $NAMESPACE
  labels:
    app.kubernetes.io/name: desk-ai
    desk.ai/pvc: $PVC_NAME
  annotations:
    desk.ai/backup-policy: csi-volume-snapshot
spec:
  volumeSnapshotClassName: $VOLUME_SNAPSHOT_CLASS_NAME
  source:
    persistentVolumeClaimName: $PVC_NAME
YAML
}

if [[ -n "$OUTPUT_FILE" ]]; then
  render > "$OUTPUT_FILE"
  echo "Rendered VolumeSnapshot $SNAPSHOT_NAME for PVC $PVC_NAME to $OUTPUT_FILE."
else
  render
fi
