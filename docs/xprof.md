# Profile a TPU notebook with XProf

The student and TA notebook image includes XProf and TensorBoard. The **XProf**
tile in the JupyterLab launcher starts a TensorBoard process inside that user's
notebook Pod and opens its **Profile** tab through the authenticated JupyterHub
route. Each user's traces are stored in their persistent `~/xprof` directory.

## Capture and view a trace

Run this in a TPU notebook cell, substituting the operations you want to profile:

```python
from pathlib import Path
import jax
import jax.numpy as jnp

logdir = str(Path.home() / "xprof")
with jax.profiler.trace(logdir):
    x = jnp.ones((1024, 1024))
    (x @ x).block_until_ready()
```

The `block_until_ready()` call makes sure TPU execution finishes while the
trace is active. Then open **XProf** from the JupyterLab launcher, or visit
`https://llmsys11868.duckdns.org/user/USERNAME/xprof/` with your JupyterHub
username in place of `USERNAME`. Select the captured session in
the **Profile** tab. The launcher starts TensorBoard on first use; no terminal
command or separately exposed port is required.

The HW0 notebook uses this JAX trace context manager. The
[JAX profiling guide](https://docs.jax.dev/en/latest/profiling.html#programmatic-capture)
documents it for capture, while the
[XProf demo](https://openxla.org/xprof/xprof_demo) uses `%tensorboard` to view
profiles. There is no documented `%%xprof` cell magic. The per-user launcher
already opens the viewer through JupyterHub, so students can profile the code
in the original `hw0_tpu_hello.ipynb` without installing a notebook extension.

Traces count against the 32 GiB home volume. Delete old traces from `~/xprof`
when they are no longer needed. The TensorBoard process ends when the notebook
server stops; the traces remain on the home volume.

The first spawn after this revision replaces `~/hw0_tpu_hello.ipynb` once. If
the student already had that file, its previous contents are saved as
`~/.course-backups/hw0_tpu_hello_before_link_only.ipynb`. The old
`hw0_tpu_hello_xprof.ipynb` copy is moved into that hidden backup directory.
Existing traces stay in `~/xprof`. Later spawns do not replace the student's
revised notebook or its outputs.

## Two-stage deployment

1. Run `make image`, then `make smoke`. The smoke Pod uses the new image on a
   v5e TPU and checks that JAX writes an XProf trace.
2. Run `make hub` to put the new image and launcher in the shared JupyterHub
   profile. Existing notebook Pods keep their old image and must be stopped and
   started again. Verify the launcher and Profile tab through IAP with one
   student account and one TA or staff account.

The existing IAP student and TA groups share this profile. Staff outside those
groups need an IAP grant before they can access JupyterHub. No extra Ingress or
public TensorBoard Service is needed.
