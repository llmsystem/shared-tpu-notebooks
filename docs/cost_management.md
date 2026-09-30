# Cost management for attached TPU notebooks

Each open student or TA JupyterLab Pod has one v5e TPU chip attached. The chip remains allocated while the server is running, including when the user is only reading or editing. Budget for the number of **simultaneously open notebooks**, not just the time spent executing code. Check current GCP pricing for the chosen region before deployment.

## Controls in this repository

1. `MAX_TPU_NOTEBOOKS` becomes the namespace's `requests.google.com/tpu` ResourceQuota. One notebook requests one chip. When the cap is reached, another spawn is rejected; users are not placed in a Kueue queue.
2. The JupyterHub idle culler stops servers after 30 minutes without activity and after a maximum age of eight hours. Check the culler behavior with real class workloads before changing these values.
3. A user's 32 GiB home volume persists after the server stops. This retains work but continues to incur disk storage charges.
4. `make smoke` deletes its short-lived TPU test Pod after the check finishes.

Users should click the red **Stop TPU Server** button in JupyterLab when they finish. It returns them to Hub home after the TPU server stops. Closing the browser tab alone may leave a TPU allocated until culling.

## Per-user usage in the admin console

The JupyterHub **Admin** page shows each Hub user's running server count, notebook
hours, and estimated TPU cost for the last 30 days and all tracked time. The Hub
records successful notebook starts and stops on its persistent database volume.
Tracking begins after the usage feature is deployed; earlier sessions cannot be
reconstructed. A server stopped outside JupyterHub is reconciled when an admin
opens the usage table, using that observation time as its estimated stop time.

Set `TPU_HOURLY_USD` in `config.env` to the effective v5e chip-hour rate for the
deployment. The default estimate is `$1.35` per chip-hour; verify the current rate
for your region and billing agreement. This table estimates attached TPU time,
including idle time. It does not reproduce a Cloud Billing invoice: persistent home
disks, shared Hub resources, network traffic, discounts, and taxes are excluded.
Only Hub administrators can read the usage endpoint.

## End-of-term cleanup

```bash
make clean-pvcs-dry-run  # inspect retained home volumes
make clean-pvcs          # delete them when their contents are no longer needed
make teardown            # delete the cluster and static IP
```

The retained queued-Job prototype and warm-pool scripts are not part of the direct-notebook deployment path.
