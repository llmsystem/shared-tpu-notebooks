#!/usr/bin/env bash
# Test every notebook topology enabled in config.env, one Pod at a time.
source "$(dirname "$0")/common.sh"
configure_tpu_topologies
require_project
check_prereqs gcloud kubectl
ensure_k8s_context

for SMOKE_TOPOLOGY in "${ENABLED_TPU_TOPOLOGIES[@]}"; do
  # Each subshell cleans up its own Pod, including on failure.
  (
    case "${SMOKE_TOPOLOGY}" in
      1x1) TPU_CHIPS=1; SMOKE_CPU_REQUEST=4; SMOKE_CPU_LIMIT=8;
           SMOKE_MEMORY_REQUEST=16Gi; SMOKE_MEMORY_LIMIT=32Gi ;;
      2x2) TPU_CHIPS=4; SMOKE_CPU_REQUEST=8; SMOKE_CPU_LIMIT=16;
           SMOKE_MEMORY_REQUEST=32Gi; SMOKE_MEMORY_LIMIT=64Gi ;;
    esac
    K=(kubectl --context="${GKE_CTX}" -n "${NAMESPACE}")
    NAME="tpu-notebook-smoke-${RANDOM}"
    IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/course-images/scipy-notebook:latest"

    cleanup() {
      "${K[@]}" delete pod "${NAME}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    }
    trap cleanup EXIT

    log_header "Testing ${TPU_CHIPS}-chip v5e access (${SMOKE_TOPOLOGY}) with ${IMAGE}"
    "${K[@]}" apply -f - <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${NAME}
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  runtimeClassName: gvisor
  priorityClassName: student-notebook
  nodeSelector:
    cloud.google.com/gke-tpu-accelerator: tpu-v5-lite-podslice
    cloud.google.com/gke-tpu-topology: ${SMOKE_TOPOLOGY}
  tolerations:
    - key: google.com/tpu
      operator: Exists
      effect: NoSchedule
  containers:
    - name: check
      image: ${IMAGE}
      env:
        - name: JAX_PLATFORMS
          value: tpu
      command: ["python3", "-c"]
      args:
        - |
          from pathlib import Path
          from tempfile import TemporaryDirectory
          import jax
          import jax.numpy as jnp
          import xprof
          import tensorboard
          import jupyter_server_proxy

          devices = jax.devices()
          assert devices and all(device.platform == "tpu" for device in devices), devices
          assert len(devices) == ${TPU_CHIPS}, devices
          print("TPU notebook image ready:", devices, flush=True)
          result = jax.pmap(lambda x: jax.lax.psum(x, "chips"), axis_name="chips")(
              jnp.arange(1, ${TPU_CHIPS} + 1, dtype=jnp.float32)
          )
          result.block_until_ready()
          assert len(result.sharding.device_set) == ${TPU_CHIPS}, result.sharding
          assert bool(jnp.all(result == ${TPU_CHIPS} * (${TPU_CHIPS} + 1) / 2)), result
          print("Cross-chip reduction ready:", result, flush=True)
          with TemporaryDirectory() as logdir:
              with jax.profiler.trace(logdir):
                  x = jnp.ones((1024, 1024))
                  (x @ x).block_until_ready()
              traces = list(Path(logdir).rglob("*.xplane.pb"))
              assert traces, "JAX did not write an XProf trace"
              print("XProf TPU trace ready:", len(traces), "file(s)", flush=True)
      resources:
        requests:
          cpu: "${SMOKE_CPU_REQUEST}"
          memory: ${SMOKE_MEMORY_REQUEST}
          google.com/tpu: "${TPU_CHIPS}"
        limits:
          cpu: "${SMOKE_CPU_LIMIT}"
          memory: ${SMOKE_MEMORY_LIMIT}
          google.com/tpu: "${TPU_CHIPS}"
YAML

    for _ in $(seq 1 90); do
      PHASE=$("${K[@]}" get pod "${NAME}" -o jsonpath='{.status.phase}')
      case "${PHASE}" in
        Succeeded)
          "${K[@]}" logs "${NAME}"
          log_success "The notebook image can run JAX on ${TPU_CHIPS} v5e chip(s)."
          exit 0
          ;;
        Failed)
          "${K[@]}" logs "${NAME}" || true
          "${K[@]}" describe pod "${NAME}"
          exit 1
          ;;
      esac
      sleep 10
    done

    "${K[@]}" describe pod "${NAME}"
    log_error "Timed out waiting for a TPU Pod after 15 minutes."
    exit 1
  )
done
