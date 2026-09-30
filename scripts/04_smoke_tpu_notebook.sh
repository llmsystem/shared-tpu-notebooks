#!/usr/bin/env bash
# Run JAX in a Pod with the same image and TPU settings as a Jupyter notebook.
source "$(dirname "$0")/common.sh"
require_project
check_prereqs gcloud kubectl
ensure_k8s_context

K=(kubectl --context="${GKE_CTX}" -n "${NAMESPACE}")
NAME="tpu-notebook-smoke-${RANDOM}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/course-images/scipy-notebook:latest"

cleanup() {
  "${K[@]}" delete pod "${NAME}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

log_header "Testing direct v5e access with ${IMAGE}"
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
    cloud.google.com/gke-tpu-topology: 1x1
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
          import jax
          devices = jax.devices()
          assert devices and all(device.platform == "tpu" for device in devices), devices
          print("TPU notebook image ready:", devices, flush=True)
      resources:
        requests:
          cpu: "4"
          memory: 16Gi
          google.com/tpu: "1"
        limits:
          cpu: "8"
          memory: 32Gi
          google.com/tpu: "1"
YAML

for _ in $(seq 1 90); do
  PHASE=$("${K[@]}" get pod "${NAME}" -o jsonpath='{.status.phase}')
  case "${PHASE}" in
    Succeeded)
      "${K[@]}" logs "${NAME}"
      log_success "The notebook image can run JAX on a v5e TPU."
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
