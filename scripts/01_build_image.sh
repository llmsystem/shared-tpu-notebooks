#!/usr/bin/env bash
# ==============================================================================
# Script: 01_build_image.sh
# Description: Build and push the custom course Docker image.
#
# The image extends scipy-notebook with JAX TPU dependencies so both course
# groups can run TPU code directly in JupyterLab.
#
# Usage:
#   make image
# ==============================================================================

source "$(dirname "$0")/common.sh"
require_project
check_prereqs gcloud docker

REPO="${REGION}-docker.pkg.dev/${PROJECT}/course-images"
IMAGE="${REPO}/scipy-notebook:latest"

log_header "Building & Pushing Course Docker Image"
log_info "Target Image: ${IMAGE}"

if ! gcloud artifacts repositories describe course-images --location="${REGION}" --project="${PROJECT}" >/dev/null 2>&1; then
  log_info "Creating Artifact Registry repository 'course-images' in ${REGION}..."

  # Cleanup policy: automatically delete untagged images older than 30 days.
  # Without this, stale image layers accumulate indefinitely and bill for storage.
  CLEANUP_POLICY=$(mktemp)
  trap 'rm -f "${CLEANUP_POLICY}"' EXIT
  cat > "${CLEANUP_POLICY}" <<'POLICY'
[
  {
    "name": "delete-untagged",
    "action": {"type": "Delete"},
    "condition": {
      "tagState": "untagged",
      "olderThan": "30d"
    }
  },
  {
    "name": "keep-recent-tagged",
    "action": {"type": "Keep"},
    "mostRecentVersions": {
      "keepCount": 5
    }
  }
]
POLICY

  gcloud artifacts repositories create course-images \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker repository for course images" \
    --project="${PROJECT}"

  echo "    applying cleanup policies..."
  gcloud artifacts repositories set-cleanup-policies course-images \
    --location="${REGION}" \
    --project="${PROJECT}" \
    --policy="${CLEANUP_POLICY}" \
    --no-dry-run
fi

echo "==> configuring docker auth for Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> building linux/amd64 image ${IMAGE} for GKE TPU nodes"
docker build --platform linux/amd64 -t "${IMAGE}" "$(dirname "$0")/../docker"

echo "==> pushing image"
docker push "${IMAGE}"

echo
echo "Done. make hub uses this image for every student and TA notebook."
