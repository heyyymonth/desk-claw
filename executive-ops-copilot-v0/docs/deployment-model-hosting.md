# Deployment Model Hosting

This document defines the production model-runtime choices for Desk AI. All options keep the same application contract: FastAPI calls Google ADK, ADK uses an Ollama-compatible model endpoint, and the required model remains `gemma4:latest` unless a separate model-change ticket updates the evals, warmup checks, and rollout runbook.

## Current Invariant

```text
LLM_MODE=ollama
OLLAMA_MODEL=gemma4:latest
ADK_MODEL=ollama_chat/gemma4:latest
```

The frontend never calls the model endpoint. Public traffic reaches the frontend Ingress, the frontend proxies `/api` to FastAPI, and FastAPI owns model warmup, ADK orchestration, validation, and telemetry.

## Supported Hosting Modes

| Mode | Kubernetes path | When to use | Cluster dependency |
| --- | --- | --- | --- |
| In-cluster CPU Ollama | `infra/k8s` | Local/private validation and very low-concurrency pilots. | Standard nodes with enough memory and persistent volume support. |
| In-cluster NVIDIA GPU Ollama | `infra/k8s-overlays/ollama-gpu-nvidia` | First controlled public pilot where model latency must be separated from cold load time. | NVIDIA-capable node pool, GPU device plugin/runtime, and a labeled/tainted model node. |
| External private Ollama-compatible endpoint | `infra/k8s-overlays/external-model` | Managed model hosting, dedicated model cluster, or an already-operated private inference endpoint. | Private network path from backend pods to the model endpoint. Do not expose the model endpoint publicly. |

When GHCR packages are private, use the composed overlays `infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia` or `infra/k8s-overlays/private-ghcr-external-model` instead of hand-merging image-pull and model-hosting patches.

Kubernetes GPU scheduling consumes vendor resources such as `nvidia.com/gpu` through device plugins, and GPU resources are specified in container limits. Ollama's Docker guidance also separates CPU, NVIDIA GPU, and AMD GPU container paths, so this repo keeps NVIDIA as one explicit overlay and leaves AMD/ROCm as a provider-specific extension.

## In-Cluster CPU

The default base deploys:

- `Deployment/ollama`
- `Service/ollama`
- `PersistentVolumeClaim/ollama-data`
- `Job/ollama-pull-gemma4`
- `NetworkPolicy/ollama-ingress`

Render a release with the base path:

```bash
REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  PUBLIC_HOST=desk-ai.example.com \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

Use this only when the CPU/memory profile has been measured. CPU-only model startup and ADK loop latency can be slow enough to look like a broken app if the operator skips warmup verification.

## In-Cluster NVIDIA GPU

The `ollama-gpu-nvidia` overlay keeps the same in-cluster Ollama service and model-pull job, then patches the Ollama deployment with:

- `nvidia.com/gpu: "1"` in container limits;
- larger CPU and memory limits for the Ollama container;
- `nodeSelector: desk-ai/model-runtime: ollama-gpu`;
- a matching `NoSchedule` toleration.

Before applying this overlay, the cluster owner must:

1. Install the provider-supported NVIDIA device plugin or GPU Operator.
2. Create a GPU node pool with enough usable VRAM for `gemma4:latest` plus runtime and context cache.
3. Label the intended GPU node or node pool:

   ```bash
   kubectl label node <gpu-node-name> desk-ai/model-runtime=ollama-gpu
   ```

4. Optionally taint the GPU node pool so only model-runtime workloads land there:

   ```bash
   kubectl taint node <gpu-node-name> desk-ai/model-runtime=ollama-gpu:NoSchedule
   ```

Render a GPU-backed release:

```bash
K8S_BASE_DIR=infra/k8s-overlays/ollama-gpu-nvidia \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  PUBLIC_HOST=desk-ai.example.com \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

If GHCR packages are private, use `K8S_BASE_DIR=infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia`. Do not hand-edit the rendered release manifest.

## External Private Model Endpoint

The `external-model` overlay removes all in-cluster Ollama resources and patches `OLLAMA_BASE_URL` to an external Ollama-compatible endpoint. It is intended for private networking, not public model exposure.

Render an external-model release:

```bash
K8S_BASE_DIR=infra/k8s-overlays/external-model \
  MODEL_ENDPOINT_URL=https://ollama.internal.example.com \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  PUBLIC_HOST=desk-ai.example.com \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

If GHCR packages are private, use `K8S_BASE_DIR=infra/k8s-overlays/private-ghcr-external-model` with the same `MODEL_ENDPOINT_URL`.

`MODEL_ENDPOINT_URL` is required for this overlay. The release renderer fails if the external overlay is selected without it, so a production manifest cannot silently keep the placeholder or point back at `http://ollama:11434`.

The external endpoint must provide the Ollama API shape used by the backend, including model availability through `gemma4:latest`. If the endpoint needs authentication, add the backend Secret contract and client support before using this mode for public traffic.

## Verification

After rollout, check the model runtime through the public app boundary:

```bash
./scripts/check-model-runtime.sh https://desk-ai.example.com
```

For GPU mode:

```bash
MODEL_HOSTING_MODE=gpu ./scripts/check-model-runtime.sh https://desk-ai.example.com
```

For external mode:

```bash
MODEL_HOSTING_MODE=external ./scripts/check-model-runtime.sh https://desk-ai.example.com
```

The checker validates:

- `/api/health` returns `status: ok`;
- Ollama is configured;
- ADK is using `ollama_chat/gemma4:latest`;
- backend warmup reports `model_warmup.status: ready`;
- the expected in-cluster Ollama resources exist or are absent for the selected mode.

## Failure Responses

| Symptom | First response |
| --- | --- |
| GPU Ollama pod is pending. | Check the GPU device plugin, `nvidia.com/gpu` allocatable capacity, node label, and taint/toleration. |
| Backend readiness never succeeds. | Check `ollama-pull-gemma4`, `/api/health`, Ollama logs, and `OLLAMA_WARMUP_TIMEOUT_SECONDS`. |
| External mode renders but backend cannot reach the model. | Confirm private DNS, firewall/security-group rules, TLS trust, and the endpoint path from backend pods. |
| Warmup is ready but real requests time out. | Inspect ADK telemetry, model latency, ingress timeout, and `ADK_AGENT_TIMEOUT_SECONDS` before increasing all timeouts. |

## References

- [Kubernetes GPU scheduling](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [Ollama Docker runtime modes](https://docs.ollama.com/docker)
