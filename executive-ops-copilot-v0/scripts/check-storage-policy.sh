#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-storage-policy.sh <storage-class-name>

Validates the selected production StorageClass and PVC wiring.

Environment:
  NAMESPACE=desk-ai
  MODEL_HOSTING_MODE=in-cluster|gpu|external
  REQUIRE_VOLUME_EXPANSION=true
  REQUIRE_VOLUME_SNAPSHOT_CLASS=false
  VOLUME_SNAPSHOT_CLASS_NAME=<provider-snapshot-class>
  KUBECTL=kubectl
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

STORAGE_CLASS_NAME="$1"
NAMESPACE="${NAMESPACE:-desk-ai}"
MODEL_HOSTING_MODE="${MODEL_HOSTING_MODE:-in-cluster}"
REQUIRE_VOLUME_EXPANSION="${REQUIRE_VOLUME_EXPANSION:-true}"
REQUIRE_VOLUME_SNAPSHOT_CLASS="${REQUIRE_VOLUME_SNAPSHOT_CLASS:-false}"
VOLUME_SNAPSHOT_CLASS_NAME="${VOLUME_SNAPSHOT_CLASS_NAME:-}"
KUBECTL="${KUBECTL:-kubectl}"

validate_name() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]; then
    echo "$label must be a valid Kubernetes DNS subdomain name." >&2
    exit 1
  fi
}

validate_bool() {
  local value="$1"
  local label="$2"
  case "$value" in
    true | false) ;;
    *)
      echo "$label must be true or false." >&2
      exit 1
      ;;
  esac
}

validate_name "$STORAGE_CLASS_NAME" "storage-class-name"
validate_bool "$REQUIRE_VOLUME_EXPANSION" "REQUIRE_VOLUME_EXPANSION"
validate_bool "$REQUIRE_VOLUME_SNAPSHOT_CLASS" "REQUIRE_VOLUME_SNAPSHOT_CLASS"

case "$MODEL_HOSTING_MODE" in
  in-cluster | gpu | external) ;;
  *)
    echo "MODEL_HOSTING_MODE must be one of: in-cluster, gpu, external." >&2
    exit 1
    ;;
esac

if [[ -n "$VOLUME_SNAPSHOT_CLASS_NAME" ]]; then
  validate_name "$VOLUME_SNAPSHOT_CLASS_NAME" "VOLUME_SNAPSHOT_CLASS_NAME"
fi

if [[ "$REQUIRE_VOLUME_SNAPSHOT_CLASS" == "true" && -z "$VOLUME_SNAPSHOT_CLASS_NAME" ]]; then
  echo "VOLUME_SNAPSHOT_CLASS_NAME must be set when REQUIRE_VOLUME_SNAPSHOT_CLASS=true." >&2
  exit 1
fi

STORAGE_CLASS_JSON="$("$KUBECTL" get storageclass "$STORAGE_CLASS_NAME" -o json)"

printf '%s' "$STORAGE_CLASS_JSON" | STORAGE_CLASS_NAME="$STORAGE_CLASS_NAME" REQUIRE_VOLUME_EXPANSION="$REQUIRE_VOLUME_EXPANSION" ruby -rjson -e '
  payload = JSON.parse(STDIN.read)
  expected_name = ENV.fetch("STORAGE_CLASS_NAME")
  require_expansion = ENV.fetch("REQUIRE_VOLUME_EXPANSION") == "true"
  errors = []

  errors << "StorageClass name is #{payload.dig("metadata", "name").inspect}, expected #{expected_name.inspect}" unless payload.dig("metadata", "name") == expected_name
  errors << "StorageClass provisioner is missing" if payload["provisioner"].to_s.empty?
  if require_expansion && payload["allowVolumeExpansion"] != true
    errors << "StorageClass must set allowVolumeExpansion: true"
  end

  unless errors.empty?
    warn errors.join("\n")
    exit 1
  end

  puts "StorageClass #{expected_name} exists with provisioner #{payload["provisioner"]}."
  puts "StorageClass allowVolumeExpansion: #{payload["allowVolumeExpansion"] == true}"
  puts "StorageClass reclaimPolicy: #{payload["reclaimPolicy"] || "provider-default"}"
'

if [[ -n "$VOLUME_SNAPSHOT_CLASS_NAME" ]]; then
  "$KUBECTL" get volumesnapshotclass "$VOLUME_SNAPSHOT_CLASS_NAME" >/dev/null
  echo "VolumeSnapshotClass $VOLUME_SNAPSHOT_CLASS_NAME exists."
fi

check_pvc() {
  local pvc_name="$1"
  local expected_role="$2"

  "$KUBECTL" -n "$NAMESPACE" get pvc "$pvc_name" -o json |
    PVC_NAME="$pvc_name" STORAGE_CLASS_NAME="$STORAGE_CLASS_NAME" EXPECTED_ROLE="$expected_role" ruby -rjson -e '
      payload = JSON.parse(STDIN.read)
      pvc_name = ENV.fetch("PVC_NAME")
      storage_class = ENV.fetch("STORAGE_CLASS_NAME")
      expected_role = ENV.fetch("EXPECTED_ROLE")
      errors = []

      errors << "#{pvc_name} storageClassName is #{payload.dig("spec", "storageClassName").inspect}, expected #{storage_class.inspect}" unless payload.dig("spec", "storageClassName") == storage_class
      errors << "#{pvc_name} is not Bound" unless payload.dig("status", "phase") == "Bound"
      annotations = payload.dig("metadata", "annotations") || {}
      errors << "#{pvc_name} missing desk.ai/storage-role=#{expected_role}" unless annotations["desk.ai/storage-role"] == expected_role
      errors << "#{pvc_name} missing desk.ai/backup-policy annotation" if annotations["desk.ai/backup-policy"].to_s.empty?
      errors << "#{pvc_name} missing desk.ai/recovery-priority annotation" if annotations["desk.ai/recovery-priority"].to_s.empty?

      unless errors.empty?
        warn errors.join("\n")
        exit 1
      end

      puts "PVC #{pvc_name} is Bound on #{storage_class} with backup policy #{annotations["desk.ai/backup-policy"]}."
    '
}

check_pvc backend-data sqlite-state

if [[ "$MODEL_HOSTING_MODE" != "external" ]]; then
  check_pvc ollama-data model-cache
else
  if "$KUBECTL" -n "$NAMESPACE" get pvc ollama-data >/dev/null 2>&1; then
    echo "External model mode should not keep pvc/ollama-data in namespace $NAMESPACE." >&2
    exit 1
  fi
  echo "External model mode has no ollama-data PVC."
fi

echo "Storage policy check passed."
