# Deployment Resource Tuning

This document captures the current production sizing assumptions for Desk AI's Kubernetes path. It is intentionally operational: use it before choosing node shapes, timeout values, or GPU scheduling policy.

## Runtime Baseline

Desk AI is deployed as three runtime services:

| Service | Current Kubernetes baseline | Primary pressure |
| --- | --- | --- |
| `frontend` | 2 replicas, `100m` CPU request, `128Mi` memory request, `500m` CPU limit, `512Mi` memory limit | Static React/nginx traffic and `/api` proxying. |
| `backend` | 1 replica, `250m` CPU request, `512Mi` memory request, `2` CPU limit, `2Gi` memory limit | FastAPI, ADK orchestration, SQLite writes, JSON validation, request/response shaping. |
| `ollama` | 1 replica, `1` CPU request, `8Gi` memory request, `4` CPU limit, `16Gi` memory limit, `20Gi` PVC | Model load, inference latency, context/KV cache, model storage. |

The checked-in baseline is an internal pilot profile, not a broad public traffic profile. Keep the backend at one replica while it uses SQLite on a `ReadWriteOnce` PVC.

## Model Assumption

The production default remains:

```text
LLM_MODE=ollama
OLLAMA_MODEL=gemma4:latest
ADK_MODEL=ollama_chat/gemma4:latest
```

The [Ollama library](https://www.ollama.com/library/gemma4) currently lists `gemma4:latest` as a 9.6GB model with a 128K context window. Treat 9.6GB as the model artifact floor, not the total runtime memory requirement. Ollama also needs runtime memory and context cache. Larger prompts, larger context use, and concurrent requests increase memory/VRAM pressure.

## Recommended Capacity Profiles

| Profile | When to use | Node shape guidance | Expected behavior |
| --- | --- | --- | --- |
| CPU-only internal pilot | Local validation, private demos, very low concurrency. | At least 4 vCPU and 16-24Gi RAM available to the Ollama pod. Keep one backend replica and one Ollama replica. | Works, but cold load and ADK request latency can be long. Avoid exposing this profile to broad public traffic. |
| Single-GPU public pilot | First public deployment with controlled access. | GPU node with at least 16Gi usable VRAM for `gemma4:latest`, 4-8 vCPU, and 24-32Gi system RAM. Keep one Ollama pod pinned to the GPU node. | Model load should be handled at startup; request latency should mostly reflect agent/tool reasoning instead of cold model load. |
| Higher throughput | More than a small number of concurrent executive-assistant users. | Separate model node pool or external private model endpoint, managed database, queue/rate limiting, and measured autoscaling. | Do not scale backend horizontally until SQLite is replaced or isolated behind a database service with proper concurrency semantics. |

For the default `gemma4:latest`, budget VRAM above the model size. A practical first target is 16Gi usable VRAM, then validate with real Desk AI prompts and telemetry. If the model spills into system memory or CPU, latency will increase sharply. If moving to `gemma4:26b` or `gemma4:31b`, resize the GPU and memory plan before deployment.

## GPU Scheduling

The repository includes an NVIDIA GPU overlay at `infra/k8s-overlays/ollama-gpu-nvidia`. Use it only after the selected provider has GPU nodes, drivers, and the NVIDIA device plugin or GPU Operator installed.

The overlay adds a GPU limit to the `ollama` container and pins the pod to a model-runtime node pool:

```yaml
resources:
  requests:
    cpu: "2"
    memory: 16Gi
  limits:
    cpu: "8"
    memory: 32Gi
    nvidia.com/gpu: "1"
nodeSelector:
  desk-ai/model-runtime: ollama-gpu
```

Kubernetes expects GPU resources to be specified in `limits`; when a GPU limit is set without a separate GPU request, Kubernetes uses the limit as the request.

For AMD GPU clusters, use the provider-supported ROCm path and confirm whether the `ollama/ollama:rocm` image, device mounts, or a device plugin is required for that cluster.

Use `docs/deployment-model-hosting.md`, the official [Ollama Docker](https://docs.ollama.com/docker) docs, and the selected cloud GPU docs when translating this overlay to a specific cloud image, device plugin, or runtime class.

Keep Ollama and its model PVC on the same availability zone or node class where possible. Model pulls and cold starts become slow and brittle if the pod frequently moves across nodes without warm storage.

## Timeout Policy

The runtime has two separate timeout classes:

| Setting | Current value | Purpose | Tuning rule |
| --- | --- | --- | --- |
| `OLLAMA_WARMUP_TIMEOUT_SECONDS` | `240` | Startup model load check. Backend readiness stays unavailable until this succeeds. | Increase for CPU-only or slow disks. Do not reduce below observed cold-load p95. |
| `ADK_AGENT_TIMEOUT_SECONDS` | `180` | Bounds one user-facing ADK agent loop after the model is already warm. | Keep lower than ingress/proxy request timeout so the backend can return a controlled failure. |
| Backend readiness probe | `timeoutSeconds: 5`, `failureThreshold: 24` | Gives startup warmup up to about four minutes before the pod is considered unavailable. | Align with `OLLAMA_WARMUP_TIMEOUT_SECONDS`. |
| Backend liveness probe | `timeoutSeconds: 5`, `periodSeconds: 30` | Detects a wedged backend process after startup. | Do not make liveness aggressive during long model-backed requests. |

Ingress and load-balancer request timeouts should be at least 30 seconds longer than `ADK_AGENT_TIMEOUT_SECONDS`. If users see gateway timeouts, first inspect backend and Ollama latency before raising every timeout.

## Production Tuning Workflow

1. Deploy one immutable commit tag with the default resource baseline.
2. Wait for the Ollama model-pull job and backend rollout to finish.
3. Check backend startup model load:

   ```bash
   curl https://desk-ai.example.com/api/health
   ```

   `model_warmup.status` must be `ready`. Track `elapsed_seconds`, `ollama_total_seconds`, and `ollama_load_seconds`.

4. Run the deterministic ingress smoke test:

   ```bash
   ./scripts/smoke-deploy.sh https://desk-ai.example.com
   ```

5. Generate a small set of real workflow requests and review AI telemetry for:

   - ADK loop latency;
   - tool-call failures;
   - model errors;
   - timeout errors;
   - backend 5xx responses;
   - Ollama pod restarts or `OOMKilled` events.

6. Inspect Kubernetes pressure:

   ```bash
   kubectl -n desk-ai top pods
   kubectl -n desk-ai describe pod -l app=ollama
   kubectl -n desk-ai logs deployment/ollama --tail=100
   kubectl -n desk-ai describe pod -l app=backend
   ```

7. Tune one constraint at a time: Ollama memory/VRAM first, then CPU, then ADK timeout, then ingress timeout.

## Failure Signals

| Signal | Likely cause | First response |
| --- | --- | --- |
| Backend never becomes ready. | Ollama not reachable, model pull missing, or warmup timeout too low. | Check `ollama-pull-gemma4`, Ollama logs, and `/api/health` model warmup fields. |
| Ollama pod is `OOMKilled`. | Model plus runtime/context cache exceeds memory limit. | Increase Ollama memory, reduce context/concurrency, or move to a larger GPU profile. |
| Requests time out but health is ready. | ADK loop or model inference exceeds `ADK_AGENT_TIMEOUT_SECONDS`. | Inspect AI telemetry, count tool/model calls, and compare with Ollama logs before raising the timeout. |
| High backend CPU with low Ollama CPU/GPU. | JSON validation, telemetry persistence, or route-level concurrency pressure. | Scale only after replacing SQLite or moving shared state to a managed database. |
| GPU is not used. | Missing device plugin/runtime, wrong image path for accelerator type, or no GPU resource assigned. | Validate node GPU visibility and add a provider-specific Ollama overlay. |

## Guardrails

- Do not call Ollama directly from the frontend. FastAPI remains the model and orchestration boundary.
- Do not disable startup warmup in production. It separates model load time from the first user request.
- Do not use `latest` image tags for production rollouts; use `git-<sha>` release renders.
- Do not scale backend replicas while the runtime database is SQLite on a single PVC.
- Do not expose admin telemetry publicly until production auth/session work is complete.
