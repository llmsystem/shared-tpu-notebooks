# LLM Systems TPU notebooks

This repository deploys JupyterHub for CMU 11-868 LLM Systems on GKE Autopilot. Every authorized student and TA receives the same JupyterLab environment with **one Cloud TPU v5e chip attached directly to the notebook Pod**. Code runs on the TPU from ordinary notebook cells; there is no Kueue queue or Job submission step in the deployed path.

A notebook holds its chip for its entire session, including idle time. The Hub stops a session after 30 minutes of inactivity or eight hours of age. Users should stop their server when finished.

## Deployment flow

```text
Student or TA → Google IAP → JupyterHub → JupyterLab Pod + one v5e TPU
                                                ↳ persistent 32 GiB home volume
```

The Hub uses an image built from [docker/Dockerfile](docker/Dockerfile) with JupyterLab and JAX TPU dependencies. The notebook Pod requests one TPU and a `1x1` v5e topology. GKE Autopilot provisions a TPU node for the Pod. The regional TPU quota and physical capacity must cover simultaneous notebooks; the namespace's `requests.google.com/tpu` ResourceQuota sets a hard local cap. Reaching that cap rejects new spawns rather than queuing them.

## Set up

Read the [step-by-step guide](docs/getting_started.md). In the repository root:

1. Copy `config.env.example` to `config.env` and set your GCP project ID, region, `NAMESPACE=llmsys`, `MAX_TPU_NOTEBOOKS`, and the student/TA Google Groups. `MAX_TPU_NOTEBOOKS` should include staff who will have a notebook open. `config.env` is ignored by Git.
2. Authenticate with `gcloud`, then run `make preflight` to check regional v5e quota and accelerator types.
3. Run `make image`, `make cluster`, and `make hub`.
4. Run `make smoke` to check that the course image can use a TPU in a sandboxed Pod.
5. Run `make iap`, configure the project's OAuth branding screen, and wait for the managed HTTPS certificate.
6. Sign in through the IAP URL as a student and as a TA. Open `hw0_tpu_hello.ipynb` and run its first cell. It must print a TPU device.

The student and TA groups get the same notebook profile. IAP controls who can reach the Hub; `ADMIN_USERS` grants Hub administration separately.

## Capacity and cost

Each open notebook consumes one v5e chip and one TPU node until the server stops. `MAX_TPU_NOTEBOOKS` is a Kubernetes cap, not a reservation or a guarantee of available hardware. The quota in [scripts/02_create_cluster.sh](scripts/02_create_cluster.sh) also allows 100 Pods, 40 PVCs, and 1 TiB of requested storage; raise those values before enrolling a larger class. Each new user home volume is 32 GiB and persists after the notebook stops.

Use `make clean-pvcs-dry-run` to inspect retained home volumes and `make clean-pvcs` only when their contents can be deleted. `make teardown` removes the cluster and static IP. See [cost management](docs/cost_management.md) for the cost behavior of attached notebooks.

## Repository layout

- `k8s/jupyterhub-values.yaml`: single direct-TPU profile, authentication, network policy, storage, and culling.
- `scripts/00_preflight.sh`, `01_build_image.sh`, `02_create_cluster.sh`, `03_deploy_hub.sh`, `04_smoke_tpu_notebook.sh`, `08_setup_iap.sh`: active deployment path.
- `notebooks/hw0_tpu_hello.ipynb`: starter notebook that checks the attached TPU and runs JAX directly.
- `notebooks/submit_tpu.py`, `k8s/kueue-tpu-queues.yaml`, and the batch testing scripts: earlier queued-Job prototype retained for development. The Makefile does not deploy or call them.

See the [architecture](docs/architecture.md) and [troubleshooting](docs/troubleshooting.md) guides for details.
