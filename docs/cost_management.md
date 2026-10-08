# Cost management for attached TPU notebooks

Each open student or TA JupyterLab Pod has one v5e TPU chip attached. The chip remains allocated while the server is running, including when the user is only reading or editing. Budget for the number of **simultaneously open notebooks**, not just the time spent executing code. Check current GCP pricing for the chosen region before deployment.

## Controls in this repository

1. `MAX_TPU_NOTEBOOKS` becomes the namespace's `requests.google.com/tpu` ResourceQuota. One notebook requests one chip. When the cap is reached, another spawn is rejected; users are not placed in a Kueue queue.
2. The JupyterHub idle culler stops servers after 30 minutes without activity and after a maximum age of eight hours. Check the culler behavior with real class workloads before changing these values.
3. A user's 32 GiB home volume persists after the server stops. This retains work but continues to incur disk storage charges.
4. `make smoke` deletes its short-lived TPU test Pod after the check finishes.

Users should click the red **Stop TPU Server** button in JupyterLab when they finish. It returns them to Hub home after the TPU server stops. **Log Out** clears the Hub session but leaves the TPU server running; closing the browser tab alone may also leave a TPU allocated until culling.

## Your usage on Hub home

The Hub **Home** page shows each signed-in user their own running server count,
notebook hours, and estimated TPU cost for the last 30 days and all tracked time.
Students also see their budget limit and remaining amount. Staff accounts show
that they are exempt. The home usage endpoint uses the signed-in Hub identity;
users cannot request another user's data.

## Per-user usage in the admin console

The JupyterHub **Admin** page shows each Hub user's running server count, notebook
hours, and estimated TPU cost for the last 30 days and all tracked time. The Hub
records successful notebook starts and stops on its persistent database volume.
Tracking begins after the usage feature is deployed; earlier sessions cannot be
reconstructed. A server stopped outside JupyterHub is reconciled when an admin
opens the usage table, using that observation time as its estimated stop time.

Set `TPU_HOURLY_USD` in `config.env` to the effective v5e chip-hour rate for the
deployment. The default estimate is `$1.40` per chip-hour (us-west4 on-demand
v5e base plus GKE TPU premium, rounded up as of October 2026); verify the current rate
for your region and billing agreement. This table estimates attached TPU time,
including idle time. It does not reproduce a Cloud Billing invoice: persistent home
disks, shared Hub resources, network traffic, discounts, and taxes are excluded.
Only Hub administrators can read the all-user usage endpoint.

## Per-student start limit

By default, a student cannot start a new TPU notebook server once their all-time
tracked TPU estimate reaches **$150**. Set `STUDENT_TPU_BUDGET_USD` in `config.env`
to change this default for all students, then run `make hub`. The check uses the
unrounded estimate, including time from currently running servers. Hub admins are
exempt. An existing server is not stopped when the estimate crosses the limit.

On the Hub **Admin** page, use **Save** in a student's budget column to set an
individual limit, or **Reset** to return that student to the configured default.
The individual limits persist in the Hub's usage SQLite database on its PVC and
survive Hub redeployments. The admin API requires admin privileges; a student
cannot change their own limit. If the usage ledger cannot be read or a new start
cannot be recorded, a student spawn is refused until tracking works again.

This is a course access control based on the configured hourly estimate, not a
hard Cloud Billing cap. Changing `TPU_HOURLY_USD` recalculates past tracked time
at the new rate. Prior untracked use and other GCP charges are excluded. Keep
the separate project billing alerts enabled to monitor actual spending.

## End-of-term cleanup

```bash
make clean-pvcs-dry-run  # inspect retained home volumes
make clean-pvcs          # delete them when their contents are no longer needed
make teardown            # delete the cluster and static IP
```

The retained queued-Job prototype and warm-pool scripts are not part of the direct-notebook deployment path.
