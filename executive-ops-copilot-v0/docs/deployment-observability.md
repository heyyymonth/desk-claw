# Deployment Observability

Desk AI exports runtime metrics for a Prometheus-compatible scraper while keeping raw meeting text, customer names, drafts, and audit payloads out of metric labels.

## Backend Metrics

The backend exposes Prometheus text metrics at:

```text
GET /metrics
```

This endpoint is intended for internal cluster scraping. It is not proxied by the frontend nginx `/api` path and should not be exposed directly through public ingress.

The backend Service includes scrape annotations:

```yaml
prometheus.io/scrape: "true"
prometheus.io/path: /metrics
prometheus.io/port: "8000"
```

The baseline NetworkPolicy allows pods in a `monitoring` namespace with label `app.kubernetes.io/name=prometheus` to scrape backend port `8000`. If your Prometheus installation uses different namespace or pod labels, adjust `infra/k8s/network-policy.yaml` before enabling default-deny policies.

## Exported Signals

Backend health and model readiness:

| Metric | Meaning |
| --- | --- |
| `desk_ai_backend_health_status` | `/api/health` status as a labeled gauge. |
| `desk_ai_backend_info` | Active model, runtime, and Ollama configuration as metadata labels. |
| `desk_ai_model_warmup_ready` | `1` only when startup model warmup reports `ready`. |
| `desk_ai_model_warmup_elapsed_seconds` | Backend-observed warmup duration. |
| `desk_ai_ollama_warmup_total_seconds` | Ollama-reported warmup request duration. |
| `desk_ai_ollama_warmup_load_seconds` | Ollama-reported model load duration. |

AI runtime quality:

| Metric | Meaning |
| --- | --- |
| `desk_ai_ai_events_observed` | AI audit events in the sampled telemetry window. |
| `desk_ai_ai_success_ratio` | AI workflow success ratio. |
| `desk_ai_ai_adk_coverage_ratio` | Share of AI events that used Google ADK. |
| `desk_ai_ai_tool_call_coverage_ratio` | Share of ADK events with tool traces. |
| `desk_ai_ai_latency_ms{stat="avg"}` | Average AI workflow latency. |
| `desk_ai_ai_latency_ms{stat="p95"}` | P95 AI workflow latency. |
| `desk_ai_ai_model_status_events` | Event counts by model status. |

Operation and tool health:

| Metric | Meaning |
| --- | --- |
| `desk_ai_ai_operation_events` | Event counts by AI operation. |
| `desk_ai_ai_operation_success_ratio` | Success ratio by operation. |
| `desk_ai_ai_operation_adk_coverage_ratio` | ADK coverage by operation. |
| `desk_ai_ai_operation_latency_ms` | Average latency by operation. |
| `desk_ai_ai_operation_tool_calls_avg` | Average tool calls by operation. |
| `desk_ai_ai_operation_model_status_events` | Model status counts by operation. |
| `desk_ai_ai_tool_calls` | Sampled calls by tool name. |
| `desk_ai_ai_tool_failures` | Sampled tool failures by tool name. |
| `desk_ai_ai_tool_success_ratio` | Success ratio by tool name. |
| `desk_ai_ai_tool_failure_reasons` | Tool failures by sanitized reason. |
| `desk_ai_ai_recent_failures_observed` | Recent failed or degraded AI events in the sample. |

Telemetry read health:

| Metric | Meaning |
| --- | --- |
| `desk_ai_telemetry_scrape_error` | `1` when the DB-backed telemetry read model cannot be built during scrape. The label is an exception type only, not an error message. |

## Suggested Alerts

Model not ready after rollout:

```promql
max(desk_ai_model_warmup_ready) < 1
```

High AI latency:

```promql
max(desk_ai_ai_latency_ms{stat="p95"}) > 30000
```

Tool failure spike:

```promql
sum(desk_ai_ai_tool_failures) > 0
```

ADK coverage regression:

```promql
max(desk_ai_ai_adk_coverage_ratio) < 1
```

Telemetry source unavailable:

```promql
max(desk_ai_telemetry_scrape_error) > 0
```

## Ingress Errors

Ingress errors are emitted by the ingress controller, not by the Desk AI backend. For the checked-in nginx Ingress path, scrape the ingress-nginx controller metrics and alert on `nginx_ingress_controller_requests` for the `desk-ai` namespace and `frontend` ingress.

Example 5xx rate:

```promql
sum(rate(nginx_ingress_controller_requests{namespace="desk-ai",ingress="frontend",status=~"5.."}[5m]))
```

Example 4xx rate:

```promql
sum(rate(nginx_ingress_controller_requests{namespace="desk-ai",ingress="frontend",status=~"4.."}[5m]))
```

Example p95 ingress latency:

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(nginx_ingress_controller_request_duration_seconds_bucket{namespace="desk-ai",ingress="frontend"}[5m])
  )
)
```

If the cluster uses a hyperscaler-managed ingress instead of ingress-nginx, map those same three concepts to the provider metrics: request volume, 4xx/5xx rate, and ingress/request latency.

## Verification

Local backend scrape:

```bash
curl http://127.0.0.1:8000/metrics
```

In-cluster scrape check:

```bash
kubectl -n desk-ai port-forward svc/backend 8000:8000
curl http://127.0.0.1:8000/metrics
```

Kubernetes manifest validation now checks that backend scrape annotations and the monitoring NetworkPolicy allowance render correctly:

```bash
./scripts/validate-k8s.sh
```

References:

- [Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [ingress-nginx monitoring](https://kubernetes.github.io/ingress-nginx/user-guide/monitoring/)
