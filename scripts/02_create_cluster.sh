#!/usr/bin/env bash
# ==============================================================================
# Script: 02_create_cluster.sh
# Description: Create the GKE Autopilot cluster, namespace, storage, priorities,
#              and a concurrent TPU notebook quota. Safe to re-run.
# ==============================================================================
source "$(dirname "$0")/common.sh"
require_project
check_prereqs gcloud kubectl

if [[ ! "${MAX_TPU_NOTEBOOKS}" =~ ^[1-9][0-9]*$ ]]; then
  log_error "MAX_TPU_NOTEBOOKS must be a positive integer."
  exit 1
fi

log_header "Provisioning GKE Autopilot Cluster '${CLUSTER}' in '${REGION}'"
if ! gcloud container clusters describe "${CLUSTER}" --region="${REGION}" \
       --project="${PROJECT}" >/dev/null 2>&1; then
  log_info "Creating Autopilot cluster (Rapid release channel)..."
  gcloud container clusters create-auto "${CLUSTER}" \
    --project="${PROJECT}" --region="${REGION}" \
    --release-channel=rapid \
    --network=default --subnetwork=default
else
  log_success "Cluster '${CLUSTER}' already exists."
fi

ensure_k8s_context
K=(kubectl --context="${GKE_CTX}")

# Drop noisy notebook stdout/stderr before Cloud Logging ingestion billing.
log_header "Configuring Log Exclusion Filter for Student Notebooks"
if ! gcloud logging sinks describe "_Default" --project="${PROJECT}" >/dev/null 2>&1; then
  log_warn "Could not verify default sink; skipping log exclusion."
else
  if gcloud logging sinks update "_Default" \
    --project="${PROJECT}" \
    --add-exclusion="name=student-notebook-noise,filter=resource.labels.namespace_name=~\"^(${NAMESPACE:?}|${NAMESPACE:?}-)\" AND resource.labels.pod_name=~\"^jupyter-\"" \
    2>/dev/null; then
    log_success "Log exclusion filter active for namespace '${NAMESPACE}'."
  else
    log_info "Log exclusion filter already exists or could not be updated."
  fi
fi

# JupyterHub refers to these classes before it starts its first pod.
log_header "Applying PriorityClasses"
"${K[@]}" apply -f "$(dirname "$0")/../k8s/priority-classes.yaml"

log_header "Configuring StorageClass (standard-rwo-retain)"
"${K[@]}" apply -f - <<YAML
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-rwo-retain
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-balanced
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
YAML

log_header "Configuring Namespace '${NAMESPACE}' and TPU notebook quota"
"${K[@]}" apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: ${NAMESPACE}
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: class-quota
  namespace: ${NAMESPACE}
spec:
  hard:
    requests.google.com/tpu: "${MAX_TPU_NOTEBOOKS}"
    count/pods: "100"
    count/persistentvolumeclaims: "40"
    requests.storage: "1Ti"
YAML

"${K[@]}" -n "${NAMESPACE}" get resourcequota class-quota
log_success "Direct TPU notebooks ready: at most ${MAX_TPU_NOTEBOOKS} concurrent chips."
