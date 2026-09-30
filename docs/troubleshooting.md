# Troubleshooting direct TPU notebooks

## IAP says “You don't have access”

Confirm that the account belongs to the Google Group configured in `STUDENT_GROUP` or `TA_GROUP` in `config.env`, or is listed in `ADMIN_USERS` or `TEST_ACCOUNTS`. Run `make iap` again to apply the bindings. Also configure the project's OAuth branding screen.

## A notebook stays Pending

Check the Pod and its events:

```bash
kubectl -n llmsys get pods
kubectl -n llmsys describe pod POD_NAME
kubectl -n llmsys get resourcequota class-quota
```

A direct TPU notebook needs one available v5e chip. Check regional `TPU_LITE_PODSLICE_V5` quota with `make preflight`, then check GKE capacity and the Pod events. The namespace quota `requests.google.com/tpu` can also reject a spawn after `MAX_TPU_NOTEBOOKS` chips are requested. There is no Kueue queue for notebooks.

## The notebook starts but JAX cannot find a TPU

Run `jax.devices()` in the notebook. The sole profile must request `google.com/tpu: 1` with `tpu-v5-lite-podslice` and `1x1` selectors. Run `make smoke` to test the image and TPU runtime in a separate Pod. If the smoke Pod works but the browser notebook does not, inspect the spawned Pod and Hub logs.

## Image pull or Jupyter startup fails

Run `make image` and `make hub` with the same `PROJECT` and `REGION` in `config.env`. The Hub should use `${REGION}-docker.pkg.dev/${PROJECT}/course-images/scipy-notebook:latest`. Check the Pod events for Artifact Registry permissions and the container logs for `jupyterhub-singleuser` errors.

## Autopilot rejects the metadata init container

Keep `singleuser.cloudMetadata.blockWithIptables: false` in `k8s/jupyterhub-values.yaml`. The notebook NetworkPolicy blocks metadata-server egress without the privileged init container.
