#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-public-dns.sh <public-host>

Verifies that a public DNS hostname resolves to the current Desk AI frontend Ingress load balancer.

Environment:
  NAMESPACE=desk-ai
  INGRESS_NAME=frontend
  KUBECTL=kubectl
  DIG=dig
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

NAMESPACE="${NAMESPACE:-desk-ai}"
INGRESS_NAME="${INGRESS_NAME:-frontend}"
KUBECTL="${KUBECTL:-kubectl}"
DIG="${DIG:-dig}"
PUBLIC_HOST="$(printf '%s' "${1%.}" | tr '[:upper:]' '[:lower:]')"

if [[ "$PUBLIC_HOST" =~ ^https?:// || "$PUBLIC_HOST" == */* || "$PUBLIC_HOST" == *:* ]]; then
  echo "Public host must be a DNS hostname only, without scheme, path, or port." >&2
  exit 1
fi

if ! [[ "$PUBLIC_HOST" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]]; then
  echo "Public host must be a valid lower-case DNS hostname with at least one dot." >&2
  exit 1
fi

for binary in "$KUBECTL" "$DIG" ruby; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "Required command is not available: $binary" >&2
    exit 1
  fi
done

normalize_lines() {
  sed 's/\.$//' | tr '[:upper:]' '[:lower:]' | sed '/^$/d'
}

resolve_raw() {
  local host="$1"
  local record_type="$2"
  "$DIG" +short "$host" "$record_type" | normalize_lines
}

resolve_ipv4() {
  resolve_raw "$1" A | grep -E '^[0-9]+(\.[0-9]+){3}$' || true
}

resolve_ipv6() {
  resolve_raw "$1" AAAA | grep ':' || true
}

resolve_cname() {
  resolve_raw "$1" CNAME
}

contains_line() {
  local needle="$1"
  shift
  local value
  for value in "$@"; do
    if [[ "$value" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

has_intersection() {
  local left_file="$1"
  local right_file="$2"
  comm -12 <(sort -u "$left_file") <(sort -u "$right_file") | grep -q .
}

INGRESS_JSON="$("$KUBECTL" -n "$NAMESPACE" get ingress "$INGRESS_NAME" -o json)"
mapfile -t TARGETS < <(
  printf '%s' "$INGRESS_JSON" | ruby -rjson -e '
    doc = JSON.parse(STDIN.read)
    targets = doc.dig("status", "loadBalancer", "ingress").to_a.flat_map do |row|
      [row["hostname"], row["ip"]]
    end.compact.map { |target| target.downcase.delete_suffix(".") }.uniq
    puts targets
  '
)

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "Ingress $NAMESPACE/$INGRESS_NAME has no load balancer hostname or IP yet." >&2
  exit 1
fi

mapfile -t HOST_A < <(resolve_ipv4 "$PUBLIC_HOST")
mapfile -t HOST_AAAA < <(resolve_ipv6 "$PUBLIC_HOST")
mapfile -t HOST_CNAME < <(resolve_cname "$PUBLIC_HOST")

HOST_IP_FILE="$(mktemp)"
TARGET_IP_FILE="$(mktemp)"
trap 'rm -f "$HOST_IP_FILE" "$TARGET_IP_FILE"' EXIT

printf '%s\n' "${HOST_A[@]}" "${HOST_AAAA[@]}" | sed '/^$/d' > "$HOST_IP_FILE"

echo "Ingress target(s):"
printf '  %s\n' "${TARGETS[@]}"
echo "DNS records for $PUBLIC_HOST:"
printf '  A: %s\n' "${HOST_A[*]:-(none)}"
printf '  AAAA: %s\n' "${HOST_AAAA[*]:-(none)}"
printf '  CNAME: %s\n' "${HOST_CNAME[*]:-(none)}"

for target in "${TARGETS[@]}"; do
  if [[ "$target" =~ ^[0-9]+(\.[0-9]+){3}$ || "$target" == *:* ]]; then
    if contains_line "$target" "${HOST_A[@]}" "${HOST_AAAA[@]}"; then
      echo "DNS check passed: $PUBLIC_HOST resolves directly to ingress IP $target."
      exit 0
    fi
    continue
  fi

  if contains_line "$target" "${HOST_CNAME[@]}"; then
    echo "DNS check passed: $PUBLIC_HOST CNAME points to ingress hostname $target."
    exit 0
  fi

  mapfile -t TARGET_A < <(resolve_ipv4 "$target")
  mapfile -t TARGET_AAAA < <(resolve_ipv6 "$target")
  printf '%s\n' "${TARGET_A[@]}" "${TARGET_AAAA[@]}" | sed '/^$/d' > "$TARGET_IP_FILE"

  if [[ -s "$HOST_IP_FILE" && -s "$TARGET_IP_FILE" ]] && has_intersection "$HOST_IP_FILE" "$TARGET_IP_FILE"; then
    echo "DNS check passed: $PUBLIC_HOST and ingress hostname $target resolve to at least one shared IP."
    exit 0
  fi
done

cat >&2 <<FAIL
DNS check failed: $PUBLIC_HOST does not resolve to the current ingress target.

Expected one of:
$(printf '  %s\n' "${TARGETS[@]}")

Check the DNS record in the zone owner account, wait for propagation, or confirm the ingress controller has published the final load balancer target.
FAIL
exit 1
