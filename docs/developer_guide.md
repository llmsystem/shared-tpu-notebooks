# Developer guide

The deployed path is a direct TPU JupyterHub notebook for every authorized student and TA. `make cluster` creates the cluster, namespace, storage, priorities, and TPU ResourceQuota. `make hub` enables the profiles selected by `TPU_ENABLED_TOPOLOGIES` in config.env; `make smoke` runs a short-lived TPU Pod with the course image.

## Files to change

- `k8s/jupyterhub-values.yaml`: TPU profiles, sandbox, network policy, home storage, and idle culling.
- `scripts/02_create_cluster.sh`: namespace quotas and cluster resources.
- `docker/Dockerfile` and `docker/requirements.txt`: software in each notebook.
- `notebooks/hw0_tpu_hello.ipynb`: starter notebook copied into each new user home.
- `scripts/08_setup_iap.sh` and `config.env`: access for student and TA Google Groups.

The previous `notebooks/submit_tpu.py`, Kueue manifest, and scale-test scripts are development artifacts. They are not mounted into student notebooks or installed by the active Makefile.

## Changing the TPU type

The profiles in `k8s/jupyterhub-values.yaml` and the Pod in `scripts/04_smoke_tpu_notebook.sh` both specify the TPU accelerator, topology, and `google.com/tpu` count. Update them together. Check that the JAX image and regional quota support the chosen hardware before deployment.

## Updating JupyterHub

Change `CHART_VERSION` in `scripts/03_deploy_hub.sh`, review the chart's profile and security settings, and rebuild the notebook image if the JupyterHub single-user version needs to match a new major Hub version. Validate a student and TA browser spawn after the upgrade.


## Profile access and local validation

`k8s/usage_tracker.py` checks profile access before Pod creation and stores grants
and session chip counts on the Hub PVC. Keep profile slugs stable for saved
selections. Configuration choices are documented in [config.env.example](../config.env.example).

Run local tests with the pinned Hub dependencies:

```bash
python3 -m venv /tmp/shared-tpu-tests
/tmp/shared-tpu-tests/bin/pip install -r tests/requirements.txt
/tmp/shared-tpu-tests/bin/python -m unittest discover -s tests -v
```

Tests mock Kubernetes; `make smoke` provisions real TPUs for each enabled topology.
