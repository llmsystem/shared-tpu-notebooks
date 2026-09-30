# Developer guide

The deployed path is a direct TPU JupyterHub notebook for every authorized student and TA. `make cluster` creates the cluster, namespace, storage, priorities, and TPU ResourceQuota. `make hub` deploys one JupyterHub profile; `make smoke` runs a short-lived TPU Pod with the course image.

## Files to change

- `k8s/jupyterhub-values.yaml`: TPU profile, sandbox, network policy, home storage, and idle culling.
- `scripts/02_create_cluster.sh`: namespace quotas and cluster resources.
- `docker/Dockerfile` and `docker/requirements.txt`: software in each notebook.
- `notebooks/hw0_tpu_hello.ipynb`: starter notebook copied into each new user home.
- `scripts/08_setup_iap.sh` and `config.env`: access for student and TA Google Groups.

The previous `notebooks/submit_tpu.py`, Kueue manifest, and scale-test scripts are development artifacts. They are not mounted into student notebooks or installed by the active Makefile.

## Changing the TPU type

The profile in `k8s/jupyterhub-values.yaml` and the Pod in `scripts/04_smoke_tpu_notebook.sh` both specify the TPU accelerator, topology, and `google.com/tpu` count. Update them together. Check that the JAX image and regional quota support the chosen hardware before deployment.

## Updating JupyterHub

Change `CHART_VERSION` in `scripts/03_deploy_hub.sh`, review the chart's profile and security settings, and rebuild the notebook image if the JupyterHub single-user version needs to match a new major Hub version. Validate a student and TA browser spawn after the upgrade.
