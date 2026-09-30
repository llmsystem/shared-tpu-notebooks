#!/usr/bin/env bash
# Check whether the selected region can support direct v5e notebook sessions.
# This script is read-only and creates no billable resources.
source "$(dirname "$0")/common.sh"
require_project
check_prereqs gcloud python3

log_header "Direct TPU Notebook Preflight"
log_info "Project: ${PROJECT}"
log_info "Region: ${REGION}"
log_info "Requested simultaneous notebooks: ${MAX_TPU_NOTEBOOKS}"

gcloud compute regions describe "${REGION}" --project="${PROJECT}" --format=json \
  | python3 -c '
import json
import sys
region = json.load(sys.stdin)
requested = int(sys.argv[1])
quota = next((q for q in region.get("quotas", [])
              if q.get("metric") == "TPU_LITE_PODSLICE_V5"), None)
if quota is None:
    raise SystemExit("No TPU_LITE_PODSLICE_V5 quota was reported for this region.")
limit = int(quota["limit"])
usage = int(quota.get("usage", 0))
print(f"v5e PodSlice quota: {limit} chips; in use: {usage}; free by quota: {limit - usage}")
if limit - usage < requested:
    raise SystemExit(f"Need at least {requested} free v5e chips by quota before everyone can spawn.")
' "${MAX_TPU_NOTEBOOKS}"

log_header "Checking v5e single-chip accelerator types"
FOUND=0
for Z in "${REGION}-a" "${REGION}-b" "${REGION}-c"; do
  if gcloud compute tpus accelerator-types list --zone="${Z}" --project="${PROJECT}" \
       --format="value(type)" 2>/dev/null | grep -q '^v5litepod-1$'; then
    log_success "${Z}: v5litepod-1 offered"
    FOUND=1
  else
    log_info "${Z}: v5litepod-1 not listed"
  fi
done
if [[ "${FOUND}" -eq 0 ]]; then
  log_error "No v5e single-chip type was listed in ${REGION}."
  exit 1
fi
log_info "Quota and accelerator type do not guarantee physical capacity at spawn time."
