# Set up LLM Systems TPU notebooks

Every student and TA who signs in through IAP gets the same JupyterLab notebook with one v5e TPU. These steps deploy direct TPU notebooks; Kueue is not installed. For more detailed setup instructions, see the [Google Docs guide](https://docs.google.com/document/d/1LNVRD3tSMCs6nC-eDaBpE4WnlDkbpnwt1RyO9TucAXY/edit?usp=sharing).

## 1. Prepare the project and workstation

Use a Google Cloud project with billing enabled and regional v5e TPU quota. Install `gcloud`, `kubectl`, `helm`, `docker`, `make`, and Python 3. Authenticate:

```bash
gcloud auth login
gcloud auth application-default login
```

Copy `config.env.example` to `config.env`. Set `PROJECT` to the **project ID**, `REGION` to a v5e region, and `NAMESPACE=llmsys`. Set `STUDENT_GROUP` and `TA_GROUP` to the two Google Groups that should enter through IAP, for example `group:students@example.edu`. Set `ADMIN_USERS` for Hub administrators. Both course groups get the same TPU notebook; administrators also use that profile.

Set `MAX_TPU_NOTEBOOKS` to the maximum number of simultaneous student and TA sessions you can support. One active notebook requires one chip. The Kubernetes quota rejects spawns above this number; it does not queue them. The default is 20. Review the Pod, PVC, and storage quotas in `scripts/02_create_cluster.sh` if your course is larger than the current 40-PVC / 1-TiB allocation.

## 2. Check quota and build the course image

```bash
make preflight
make image
```

`make preflight` checks the regional `TPU_LITE_PODSLICE_V5` quota and available v5e single-chip accelerator types. The image includes JupyterLab and JAX TPU dependencies, is built for the GKE nodes' `linux/amd64` architecture even on Apple silicon Macs, and is pushed to your project's Artifact Registry.

## 3. Create the cluster and deploy JupyterHub

```bash
make cluster
make hub
```

The cluster step creates GKE Autopilot, the `llmsys` namespace, a storage class, PriorityClasses, and a TPU ResourceQuota. It does not install Kueue. The Hub has one TPU notebook profile for all IAP-authorized users.

If this is an upgrade from the CPU notebook setup, stop existing user servers after
`make hub` so their next spawn uses the TPU profile. The deployment revokes the old
student Job-submission RoleBinding; it does not automatically uninstall a Kueue
controller that an older deployment may have installed.

## 4. Test direct TPU access

```bash
make smoke
```

This runs a short-lived Pod with the same course image, gVisor runtime, and one-chip v5e settings as the notebook. It should print `TPU notebook image ready:` followed by a TPU device. The smoke Pod is removed at the end.
It provisions a real TPU node and incurs usage charges while it runs.

## 5. Enable HTTPS and sign-in

```bash
make iap
```

Configure the OAuth branding screen for the project when the script prompts you. Wait for the Google-managed certificate to become active. Open the IAP URL printed by the script, sign in once with a student account and once with a TA account, and start a notebook for each. Open `hw0_tpu_hello.ipynb` and run its first cell; it must show a TPU device. This browser check confirms JupyterHub spawning as well as TPU access.

Save your notebook, then click the red **Stop TPU Server** button in JupyterLab's top bar and confirm. It stops the TPU server and returns to Hub home without spawning another server; the home volume persists. The control panel's **Log Out** button clears your JupyterHub session, revokes browser session tokens, and clears this app's Google IAP cookie. If Google asks you to choose an account, that choice signs you back into JupyterHub directly; there is no second Hub sign-in button. With one active Google account, IAP may sign you back in silently after logout. To remain signed out on a shared computer, sign out of Google or use a private browser window. The notebook server keeps running until you stop it. Closing a tab does not immediately release the TPU. Browser close events can be missed, and a refresh or another open tab should not terminate a running computation. The 30-minute inactivity culler remains the fallback; a silent long-running cell can still be culled, so checkpoint long jobs.
