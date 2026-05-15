#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-public-access.sh <public-host>

Validates the deployed frontend Ingress public access-control decision.

Environment:
  NAMESPACE=desk-ai
  INGRESS_NAME=frontend
  PUBLIC_ACCESS_MODE=ip-allowlist|provider-gated
  PUBLIC_ALLOWED_CIDRS=<cidr,cidr>                # required for ip-allowlist
  PUBLIC_WAF_POLICY_ID=<provider-policy-id>       # required for provider-gated
  PUBLIC_DDOS_PROTECTION=true                     # required for provider-gated
  PUBLIC_IDENTITY_PROVIDER=<provider-or-tenant>   # required for provider-gated
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

PUBLIC_HOST="$(printf '%s' "${1%.}" | tr '[:upper:]' '[:lower:]')"
NAMESPACE="${NAMESPACE:-desk-ai}"
INGRESS_NAME="${INGRESS_NAME:-frontend}"
PUBLIC_ACCESS_MODE="${PUBLIC_ACCESS_MODE:-}"
PUBLIC_ALLOWED_CIDRS="${PUBLIC_ALLOWED_CIDRS:-}"
PUBLIC_WAF_POLICY_ID="${PUBLIC_WAF_POLICY_ID:-}"
PUBLIC_DDOS_PROTECTION="${PUBLIC_DDOS_PROTECTION:-}"
PUBLIC_IDENTITY_PROVIDER="${PUBLIC_IDENTITY_PROVIDER:-}"
KUBECTL="${KUBECTL:-kubectl}"

if [[ "$PUBLIC_HOST" =~ ^https?:// || "$PUBLIC_HOST" == */* || "$PUBLIC_HOST" == *:* ]]; then
  echo "public-host must be a DNS hostname only, without scheme, path, or port." >&2
  exit 1
fi

if ! [[ "$PUBLIC_HOST" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]]; then
  echo "public-host must be a valid lower-case DNS hostname with at least one dot." >&2
  exit 1
fi

case "$PUBLIC_ACCESS_MODE" in
  ip-allowlist | provider-gated) ;;
  *)
    echo "PUBLIC_ACCESS_MODE must be one of: ip-allowlist, provider-gated." >&2
    exit 1
    ;;
esac

INGRESS_JSON="$("$KUBECTL" -n "$NAMESPACE" get ingress "$INGRESS_NAME" -o json)"

printf '%s' "$INGRESS_JSON" |
  PUBLIC_HOST="$PUBLIC_HOST" \
  PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" \
  PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" \
  PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" \
  PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" \
  PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" \
  ruby -rjson -ripaddr -e '
    payload = JSON.parse(STDIN.read)
    host = ENV.fetch("PUBLIC_HOST")
    mode = ENV.fetch("PUBLIC_ACCESS_MODE")
    allowed_cidrs = ENV.fetch("PUBLIC_ALLOWED_CIDRS")
    waf_policy_id = ENV.fetch("PUBLIC_WAF_POLICY_ID")
    ddos_protection = ENV.fetch("PUBLIC_DDOS_PROTECTION")
    identity_provider = ENV.fetch("PUBLIC_IDENTITY_PROVIDER")
    annotations = payload.dig("metadata", "annotations") || {}
    errors = []

    rules = payload.dig("spec", "rules").to_a
    tls = payload.dig("spec", "tls").to_a
    ingress_hosts = rules.map { |entry| entry["host"] }.compact
    tls_hosts = tls.flat_map { |entry| entry["hosts"].to_a }

    errors << "Ingress rules do not include host #{host.inspect}" unless ingress_hosts.include?(host)
    errors << "Ingress TLS hosts do not include host #{host.inspect}" unless tls_hosts.include?(host)
    errors << "desk.ai/public-access-mode is #{annotations["desk.ai/public-access-mode"].inspect}, expected #{mode.inspect}" unless annotations["desk.ai/public-access-mode"] == mode

    if mode == "ip-allowlist"
      if allowed_cidrs.empty?
        errors << "PUBLIC_ALLOWED_CIDRS must be set for ip-allowlist mode"
      else
        entries = allowed_cidrs.split(",").map(&:strip)
        entries.each do |entry|
          if !entry.include?("/")
            errors << "PUBLIC_ALLOWED_CIDRS entry #{entry.inspect} must include a prefix length"
          else
            begin
              IPAddr.new(entry)
            rescue ArgumentError
              errors << "PUBLIC_ALLOWED_CIDRS entry #{entry.inspect} is not a valid CIDR range"
            end
          end
        end
      end

      actual = annotations["nginx.ingress.kubernetes.io/whitelist-source-range"]
      errors << "nginx whitelist-source-range is #{actual.inspect}, expected #{allowed_cidrs.inspect}" unless actual == allowed_cidrs
      errors << "desk.ai/allowed-cidrs is #{annotations["desk.ai/allowed-cidrs"].inspect}, expected #{allowed_cidrs.inspect}" unless annotations["desk.ai/allowed-cidrs"] == allowed_cidrs
    end

    if mode == "provider-gated"
      errors << "PUBLIC_WAF_POLICY_ID must be set for provider-gated mode" if waf_policy_id.empty?
      errors << "PUBLIC_DDOS_PROTECTION=true must be set for provider-gated mode" unless ddos_protection == "true"
      errors << "PUBLIC_IDENTITY_PROVIDER must be set for provider-gated mode" if identity_provider.empty?
      errors << "desk.ai/waf-policy-id is #{annotations["desk.ai/waf-policy-id"].inspect}, expected #{waf_policy_id.inspect}" unless annotations["desk.ai/waf-policy-id"] == waf_policy_id
      errors << "desk.ai/ddos-protection is #{annotations["desk.ai/ddos-protection"].inspect}, expected \"true\"" unless annotations["desk.ai/ddos-protection"] == "true"
      errors << "desk.ai/identity-provider is #{annotations["desk.ai/identity-provider"].inspect}, expected #{identity_provider.inspect}" unless annotations["desk.ai/identity-provider"] == identity_provider
    end

    unless errors.empty?
      warn "Public access check failed:"
      errors.each { |error| warn "- #{error}" }
      exit 1
    end

    puts "Public access check passed for #{host}."
    puts "Access mode: #{mode}"
    puts "Allowed CIDRs: #{allowed_cidrs}" if mode == "ip-allowlist"
    puts "WAF policy: #{waf_policy_id}" if mode == "provider-gated"
    puts "Identity provider: #{identity_provider}" if mode == "provider-gated"
  '
