# Cost management for attached TPU notebooks

Each open student or TA JupyterLab Pod has one v5e TPU chip attached. The chip remains allocated while the server is running, including when the user is only reading or editing. Budget for the number of **simultaneously open notebooks**, not just the time spent executing code. Check current GCP pricing for the chosen region before deployment.

## Controls in this repository

1. `MAX_TPU_NOTEBOOKS` becomes the namespace's `requests.google.com/tpu` ResourceQuota. One notebook requests one chip. When the cap is reached, another spawn is rejected; users are not placed in a Kueue queue.
2. The JupyterHub idle culler stops servers after 30 minutes without activity and after a maximum age of eight hours. Check the culler behavior with real class workloads before changing these values.
3. A user's 32 GiB home volume persists after the server stops. This retains work but continues to incur disk storage charges.
4. `make smoke` deletes its short-lived TPU test Pod after the check finishes.

Users should stop their server from the JupyterHub control panel when they finish. Closing the browser tab alone may leave a TPU allocated until culling.

## End-of-term cleanup

```bash
make clean-pvcs-dry-run  # inspect retained home volumes
make clean-pvcs          # delete them when their contents are no longer needed
make teardown            # delete the cluster and static IP
```

The retained queued-Job prototype and warm-pool scripts are not part of the direct-notebook deployment path.
