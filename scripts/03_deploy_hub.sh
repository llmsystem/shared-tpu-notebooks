#!/usr/bin/env bash
# ==============================================================================
# Script: 03_deploy_hub.sh
# Description: Install JupyterHub with one direct-TPU notebook profile for all users.
# ==============================================================================
source "$(dirname "$0")/common.sh"
require_project
check_prereqs gcloud kubectl helm

RELEASE="${RELEASE:-hub}"
CHART_VERSION="${CHART_VERSION:-4.4.1}"

ensure_k8s_context

# Revoke the Job-submission permissions left by earlier deployments.
kubectl --context="${GKE_CTX}" -n "${NAMESPACE}" delete \
  rolebinding/student-tpu-submit role/student-tpu-submit serviceaccount/student \
  --ignore-not-found

echo "==> helm repo"
helm repo add jupyterhub https://hub.jupyter.org/helm-chart/ >/dev/null 2>&1 || true
helm repo update >/dev/null

VALUES="$(dirname "$0")/../k8s/jupyterhub-values.yaml"

IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT}/course-images/scipy-notebook"
IMAGE_TAG="latest"
TPU_HOURLY_USD="${TPU_HOURLY_USD:-1.35}"

ADMIN_USERS="${ADMIN_USERS:-instructor}"
ADMIN_LIST=()
for u in $(echo "${ADMIN_USERS}" | tr ',' ' '); do
  uname=$(echo "${u}" | sed -e 's/^user://' -e 's/@.*//')
  [[ -n "${uname}" ]] && ADMIN_LIST+=("${uname}")
done
ADMIN_STR=$(IFS=,; echo "${ADMIN_LIST[*]}")
echo "==> configured JupyterHub admin users: ${ADMIN_STR}"

echo "==> installing JupyterHub ${CHART_VERSION} into ${NAMESPACE}"
helm upgrade --install "${RELEASE}" jupyterhub/jupyterhub \
  --namespace "${NAMESPACE}" \
  --version "${CHART_VERSION}" \
  --values "${VALUES}" \
  --set singleuser.image.name="${IMAGE_NAME}" \
  --set singleuser.image.tag="${IMAGE_TAG}" \
  --set-string hub.extraEnv.TPU_HOURLY_USD="${TPU_HOURLY_USD}" \
  --set "hub.config.Authenticator.admin_users={${ADMIN_STR}}" \
  --set-file "hub.extraFiles.usageTrackerPy.stringData=$(dirname "$0")/../k8s/usage_tracker.py" \
  --set-file "hub.extraFiles.adminUsageTemplate.stringData=$(dirname "$0")/../k8s/admin-usage.html" \
  --set-file "singleuser.extraFiles.hw0_tpu_hello\.ipynb.stringData=$(dirname "$0")/../notebooks/hw0_tpu_hello.ipynb" \
  --timeout 20m \
  --wait

echo
kubectl -n "${NAMESPACE}" get pods
echo

# proxy-public is a ClusterIP now, so there is no external address to wait for. The
# earlier version of this script polled for a LoadBalancer IP for ten minutes on every
# deploy, and in this org that IP never arrives: an L4 load balancer defaults its source
# range to 0.0.0.0/0, which the org policy forbids.
#
# The hub is reached through the Ingress instead. Run 08_setup_iap.sh once per cluster.
if kubectl -n "${NAMESPACE}" get ingress hub-ingress >/dev/null 2>&1; then
  DOMAIN=$(kubectl -n "${NAMESPACE}" get managedcertificate "${HUB_CERT_NAME}" \
             -o jsonpath='{.spec.domains[0]}' 2>/dev/null || true)
  STATUS=$(kubectl -n "${NAMESPACE}" get managedcertificate "${HUB_CERT_NAME}" \
             -o jsonpath='{.status.certificateStatus}' 2>/dev/null || true)
  echo "hub: https://${DOMAIN}   (certificate: ${STATUS:-unknown})"
else
  echo "No ingress yet. Put the hub behind HTTPS and Google sign-in with:"
  echo "  bash $(dirname "$0")/08_setup_iap.sh"
fi
