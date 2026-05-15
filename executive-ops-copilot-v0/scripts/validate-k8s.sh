#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/infra/k8s"
RENDERED_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-rendered.yaml"
RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-release-rendered.yaml"
DNS_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-dns-release-rendered.yaml"
TLS_PRECREATED_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-precreated-tls-release-rendered.yaml"
RUNTIME_SECRET_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-runtime-secret-release-rendered.yaml"
PRIVATE_GHCR_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-rendered.yaml"
PRIVATE_GHCR_RELEASE_MANIFEST="${TMPDIR:-/tmp}/desk-ai-k8s-private-ghcr-release-rendered.yaml"
CERT_MANAGER_ISSUER_MANIFEST="${TMPDIR:-/tmp}/desk-ai-cert-manager-issuer-rendered.yaml"
EXTERNAL_SECRET_MANIFEST="${TMPDIR:-/tmp}/desk-ai-external-secret-rendered.yaml"
TLS_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-public-tls-check.out"
RUNTIME_SECRET_CHECK_OUTPUT="${TMPDIR:-/tmp}/desk-ai-runtime-secret-check.out"
INVALID_PUBLIC_HOST_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-public-host.err"
INVALID_TLS_MODE_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-tls-mode.err"
INVALID_ACME_EMAIL_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-acme-email.err"
INVALID_EXTERNAL_SECRET_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-external-secret.err"
INVALID_REQUIRE_RUNTIME_SECRET_ERROR="${TMPDIR:-/tmp}/desk-ai-invalid-require-runtime-secret.err"
KUBECTL="${KUBECTL:-kubectl}"

parse_yaml() {
  local manifest="$1"
  if command -v ruby >/dev/null 2>&1; then
    ruby -e 'require "yaml"; YAML.load_stream(File.read(ARGV.fetch(0)))' "$manifest"
  else
    echo "Ruby is not installed; skipping YAML stream parse." >&2
  fi
}

validate_schema() {
  local manifest="$1"
  if command -v kubeconform >/dev/null 2>&1; then
    kubeconform -strict -summary -ignore-missing-schemas "$manifest"
  else
    echo "kubeconform is not installed; skipping offline Kubernetes schema validation." >&2
  fi
}

check_common_invariants() {
  local manifest="$1"
  if grep -q "ghcr.io/OWNER" "$manifest"; then
    echo "Rendered manifests still contain placeholder GHCR image names." >&2
    exit 1
  fi

  if grep -q "type: LoadBalancer" "$manifest"; then
    echo "Rendered manifests expose a LoadBalancer service; public traffic should enter through Ingress." >&2
    exit 1
  fi

  grep -q "kind: Ingress" "$manifest" || {
    echo "Rendered manifests do not include an Ingress." >&2
    exit 1
  }

  grep -q "name: desk-ai-secrets" "$manifest" || {
    echo "Rendered manifests do not reference the runtime secret contract." >&2
    exit 1
  }

  grep -q "kind: NetworkPolicy" "$manifest" || {
    echo "Rendered manifests do not include NetworkPolicy resources." >&2
    exit 1
  }

  grep -q "name: backend-ingress" "$manifest" || {
    echo "Rendered manifests do not include the backend ingress policy." >&2
    exit 1
  }

  grep -q "prometheus.io/path: /metrics" "$manifest" || {
    echo "Rendered manifests do not include backend Prometheus scrape metadata." >&2
    exit 1
  }

  grep -q "kubernetes.io/metadata.name: monitoring" "$manifest" || {
    echo "Rendered manifests do not allow the monitoring namespace to scrape backend metrics." >&2
    exit 1
  }

  grep -q "name: ollama-ingress" "$manifest" || {
    echo "Rendered manifests do not include the Ollama ingress policy." >&2
    exit 1
  }
}

check_sqlite_replica_policy() {
  local manifest="$1"
  if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby is not installed; skipping SQLite replica policy validation." >&2
    return
  fi

  ruby -e '
    require "yaml"

    docs = YAML.load_stream(File.read(ARGV.fetch(0))).compact
    config = docs.find { |doc| doc["kind"] == "ConfigMap" && doc.dig("metadata", "name") == "desk-ai-config" }
    database_url = config&.dig("data", "DATABASE_URL").to_s
    backend = docs.find { |doc| doc["kind"] == "Deployment" && doc.dig("metadata", "name") == "backend" }
    replicas = backend&.dig("spec", "replicas")

    if database_url.start_with?("sqlite:") && replicas != 1
      warn "Backend replicas must stay at 1 while DATABASE_URL uses SQLite."
      exit 1
    end
  ' "$manifest"
}

check_private_ghcr_invariants() {
  local manifest="$1"

  grep -q "imagePullSecrets:" "$manifest" || {
    echo "Private GHCR manifests do not include imagePullSecrets." >&2
    exit 1
  }

  grep -q "name: ghcr-pull-secret" "$manifest" || {
    echo "Private GHCR manifests do not reference ghcr-pull-secret." >&2
    exit 1
  }
}

validate_manifest() {
  local manifest="$1"
  parse_yaml "$manifest"
  validate_schema "$manifest"
  check_common_invariants "$manifest"
  check_sqlite_replica_policy "$manifest"
}

for script in \
  "$ROOT_DIR/scripts/check-public-dns.sh" \
  "$ROOT_DIR/scripts/check-public-tls.sh" \
  "$ROOT_DIR/scripts/check-runtime-secret.sh" \
  "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" \
  "$ROOT_DIR/scripts/render-external-secret.sh" \
  "$ROOT_DIR/scripts/render-release-k8s.sh"; do
  bash -n "$script"
done

"$KUBECTL" kustomize "$K8S_DIR" > "$RENDERED_MANIFEST"
validate_manifest "$RENDERED_MANIFEST"

"$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$RELEASE_MANIFEST"
validate_manifest "$RELEASE_MANIFEST"

PUBLIC_HOST=desk-ai.example.test TLS_SECRET_NAME=desk-ai-example-tls "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$DNS_RELEASE_MANIFEST"
validate_manifest "$DNS_RELEASE_MANIFEST"

TLS_MODE=precreated-secret PUBLIC_HOST=desk-ai.example.test TLS_SECRET_NAME=desk-ai-manual-tls "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$TLS_PRECREATED_RELEASE_MANIFEST"
validate_manifest "$TLS_PRECREATED_RELEASE_MANIFEST"

REQUIRE_RUNTIME_SECRET=true "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$RUNTIME_SECRET_RELEASE_MANIFEST"
validate_manifest "$RUNTIME_SECRET_RELEASE_MANIFEST"

"$KUBECTL" kustomize "$ROOT_DIR/infra/k8s-overlays/private-ghcr" > "$PRIVATE_GHCR_MANIFEST"
validate_manifest "$PRIVATE_GHCR_MANIFEST"
check_private_ghcr_invariants "$PRIVATE_GHCR_MANIFEST"

K8S_BASE_DIR="infra/k8s-overlays/private-ghcr" "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee > "$PRIVATE_GHCR_RELEASE_MANIFEST"
validate_manifest "$PRIVATE_GHCR_RELEASE_MANIFEST"
check_private_ghcr_invariants "$PRIVATE_GHCR_RELEASE_MANIFEST"

if PUBLIC_HOST=https://desk-ai.example.test "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_PUBLIC_HOST_ERROR"; then
  echo "Release renderer accepted an invalid PUBLIC_HOST with scheme." >&2
  exit 1
fi

grep -q "PUBLIC_HOST must be a DNS hostname only" "$INVALID_PUBLIC_HOST_ERROR" || {
  echo "Release renderer did not explain invalid PUBLIC_HOST input." >&2
  exit 1
}

if TLS_MODE=invalid PUBLIC_HOST=desk-ai.example.test "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_TLS_MODE_ERROR"; then
  echo "Release renderer accepted an invalid TLS_MODE." >&2
  exit 1
fi

grep -q "TLS_MODE must be one of" "$INVALID_TLS_MODE_ERROR" || {
  echo "Release renderer did not explain invalid TLS_MODE input." >&2
  exit 1
}

if REQUIRE_RUNTIME_SECRET=maybe "$ROOT_DIR/scripts/render-release-k8s.sh" git-deadbee >/dev/null 2>"$INVALID_REQUIRE_RUNTIME_SECRET_ERROR"; then
  echo "Release renderer accepted an invalid REQUIRE_RUNTIME_SECRET value." >&2
  exit 1
fi

grep -q "REQUIRE_RUNTIME_SECRET must be true or false" "$INVALID_REQUIRE_RUNTIME_SECRET_ERROR" || {
  echo "Release renderer did not explain invalid REQUIRE_RUNTIME_SECRET input." >&2
  exit 1
}

if ACME_ENV=staging "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" letsencrypt-staging >/dev/null 2>"$INVALID_ACME_EMAIL_ERROR"; then
  echo "ClusterIssuer renderer accepted missing ACME_EMAIL." >&2
  exit 1
fi

grep -q "ACME_EMAIL must be set" "$INVALID_ACME_EMAIL_ERROR" || {
  echo "ClusterIssuer renderer did not explain missing ACME_EMAIL input." >&2
  exit 1
}

ACME_EMAIL=ops@example.com ACME_ENV=staging "$ROOT_DIR/scripts/render-cert-manager-issuer.sh" letsencrypt-staging > "$CERT_MANAGER_ISSUER_MANIFEST"
parse_yaml "$CERT_MANAGER_ISSUER_MANIFEST"
validate_schema "$CERT_MANAGER_ISSUER_MANIFEST"

grep -q "kind: ClusterIssuer" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not render a ClusterIssuer." >&2
  exit 1
}

grep -q "server: https://acme-staging-v02.api.letsencrypt.org/directory" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not use the Let's Encrypt staging server." >&2
  exit 1
}

grep -q "ingressClassName: nginx" "$CERT_MANAGER_ISSUER_MANIFEST" || {
  echo "ClusterIssuer renderer did not configure the nginx HTTP-01 ingress solver." >&2
  exit 1
}

if "$ROOT_DIR/scripts/render-external-secret.sh" >/dev/null 2>"$INVALID_EXTERNAL_SECRET_ERROR"; then
  echo "ExternalSecret renderer accepted a missing SECRET_STORE_NAME." >&2
  exit 1
fi

grep -q "SECRET_STORE_NAME must be set" "$INVALID_EXTERNAL_SECRET_ERROR" || {
  echo "ExternalSecret renderer did not explain missing SECRET_STORE_NAME input." >&2
  exit 1
}

SECRET_STORE_NAME=desk-ai-runtime-secrets REMOTE_SECRET_KEY=desk-ai/production/runtime "$ROOT_DIR/scripts/render-external-secret.sh" > "$EXTERNAL_SECRET_MANIFEST"
parse_yaml "$EXTERNAL_SECRET_MANIFEST"
validate_schema "$EXTERNAL_SECRET_MANIFEST"

grep -q "kind: ExternalSecret" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not render an ExternalSecret." >&2
  exit 1
}

grep -q "name: desk-ai-runtime-secrets" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not use the requested SecretStore name." >&2
  exit 1
}

grep -q "key: desk-ai/production/runtime" "$EXTERNAL_SECRET_MANIFEST" || {
  echo "ExternalSecret renderer did not use the requested remote secret key." >&2
  exit 1
}

TLS_CHECK_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-tls-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR"' EXIT

cat > "$TLS_CHECK_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"get ingress frontend -o json"*)
    cat <<'JSON'
{"spec":{"tls":[{"hosts":["desk-ai.example.test"],"secretName":"desk-ai-example-tls"}]}}
JSON
    ;;
  *"get secret desk-ai-example-tls -o json"*)
    cat <<'JSON'
{"type":"kubernetes.io/tls","data":{"tls.crt":"Y2VydA==","tls.key":"a2V5"}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

cat > "$TLS_CHECK_FAKE_DIR/openssl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "Verify return code: 0 (ok)"
SH

chmod +x "$TLS_CHECK_FAKE_DIR/kubectl" "$TLS_CHECK_FAKE_DIR/openssl"

KUBECTL="$TLS_CHECK_FAKE_DIR/kubectl" OPENSSL="$TLS_CHECK_FAKE_DIR/openssl" TLS_SECRET_NAME=desk-ai-example-tls "$ROOT_DIR/scripts/check-public-tls.sh" desk-ai.example.test > "$TLS_CHECK_OUTPUT"

grep -q "Public HTTPS certificate validates for desk-ai.example.test" "$TLS_CHECK_OUTPUT" || {
  echo "Public TLS check did not validate the fake HTTPS certificate." >&2
  exit 1
}

RUNTIME_SECRET_FAKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/desk-ai-runtime-secret-check.XXXXXX")"
trap 'rm -rf "$TLS_CHECK_FAKE_DIR" "$RUNTIME_SECRET_FAKE_DIR"' EXIT

cat > "$RUNTIME_SECRET_FAKE_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  *"get secret desk-ai-secrets -o json"*)
    cat <<'JSON'
{"type":"Opaque","data":{"ADMIN_API_KEY":"cmVhbC1hZG1pbi10b2tlbg==","ACTOR_AUTH_TOKEN":"cmVhbC1hY3Rvci10b2tlbg=="}}
JSON
    ;;
  *"get deployment backend -o json"*)
    cat <<'JSON'
{"spec":{"template":{"spec":{"containers":[{"name":"backend","envFrom":[{"configMapRef":{"name":"desk-ai-config"}},{"secretRef":{"name":"desk-ai-secrets","optional":false}}]}]}}}}
JSON
    ;;
  *)
    echo "unexpected kubectl args: $*" >&2
    exit 1
    ;;
esac
SH

chmod +x "$RUNTIME_SECRET_FAKE_DIR/kubectl"

KUBECTL="$RUNTIME_SECRET_FAKE_DIR/kubectl" "$ROOT_DIR/scripts/check-runtime-secret.sh" desk-ai-secrets > "$RUNTIME_SECRET_CHECK_OUTPUT"

grep -q "Secret desk-ai-secrets contains required key" "$RUNTIME_SECRET_CHECK_OUTPUT" || {
  echo "Runtime Secret check did not validate required Secret keys." >&2
  exit 1
}

grep -q "Deployment backend references Secret desk-ai-secrets" "$RUNTIME_SECRET_CHECK_OUTPUT" || {
  echo "Runtime Secret check did not validate backend deployment wiring." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-backend:git-deadbee" "$RELEASE_MANIFEST" || {
  echo "Release manifests do not use the requested immutable backend image tag." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-frontend:git-deadbee" "$RELEASE_MANIFEST" || {
  echo "Release manifests do not use the requested immutable frontend image tag." >&2
  exit 1
}

if grep -q "ghcr.io/heyyymonth/desk-ai-.*:latest" "$RELEASE_MANIFEST"; then
  echo "Release manifests still contain mutable latest application image tags." >&2
  exit 1
fi

grep -q "host: desk-ai.example.test" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not use the requested public host." >&2
  exit 1
}

grep -q "secretName: desk-ai-example-tls" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not use the requested TLS Secret name." >&2
  exit 1
}

if grep -q "desk-ai.example.com" "$DNS_RELEASE_MANIFEST"; then
  echo "DNS release manifests still contain the placeholder ingress hostname." >&2
  exit 1
fi

grep -q "cert-manager.io/cluster-issuer: letsencrypt-prod" "$DNS_RELEASE_MANIFEST" || {
  echo "DNS release manifests do not keep the default cert-manager ClusterIssuer." >&2
  exit 1
}

grep -q "secretName: desk-ai-manual-tls" "$TLS_PRECREATED_RELEASE_MANIFEST" || {
  echo "Pre-created TLS release manifests do not use the requested TLS Secret name." >&2
  exit 1
}

if grep -q "cert-manager.io/cluster-issuer" "$TLS_PRECREATED_RELEASE_MANIFEST"; then
  echo "Pre-created TLS release manifests still include the cert-manager ClusterIssuer annotation." >&2
  exit 1
fi

grep -q "name: desk-ai-secrets" "$RUNTIME_SECRET_RELEASE_MANIFEST" || {
  echo "Runtime-secret release manifests do not reference the requested backend Secret name." >&2
  exit 1
}

grep -q "optional: false" "$RUNTIME_SECRET_RELEASE_MANIFEST" || {
  echo "Runtime-secret release manifests do not require the backend Secret." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-backend:git-deadbee" "$PRIVATE_GHCR_RELEASE_MANIFEST" || {
  echo "Private GHCR release manifests do not use the requested immutable backend image tag." >&2
  exit 1
}

grep -q "ghcr.io/heyyymonth/desk-ai-frontend:git-deadbee" "$PRIVATE_GHCR_RELEASE_MANIFEST" || {
  echo "Private GHCR release manifests do not use the requested immutable frontend image tag." >&2
  exit 1
}

if grep -q "ghcr.io/heyyymonth/desk-ai-.*:latest" "$PRIVATE_GHCR_RELEASE_MANIFEST"; then
  echo "Private GHCR release manifests still contain mutable latest application image tags." >&2
  exit 1
fi

echo "Kubernetes manifests rendered and validated successfully."
