# Advanced v5e notebooks

Both profiles use the same JupyterLab image and persistent home volume.
Configuration options are documented in [config.env.example](../config.env.example).

| Profile | v5e chips | Topology |
| --- | --- | --- |
| Standard | 1 | `1x1` |
| Advanced | 4 | `2x2` |

## Access and switching

On the Hub **Admin** page, choose a user's **Notebook access** and click
**Save access**. Four-chip access requires a grant, including for administrators.
Users appear after their first login. Grants persist across Hub redeployments.

Access changes apply to the next start. Revocation blocks saved and API selections
but leaves running servers active; use the Admin stop control to stop them.
To switch profiles, save your work, stop the server, and start again. Home files
persist, and the one-chip profile is the default when enabled.

## Capacity and validation

`MAX_TPU_NOTEBOOKS` caps chips: `standard_sessions + 4 * advanced_sessions`.
Four-chip sessions use four times the chip-hours and estimated cost per server
hour. Existing one-chip usage history and student budget limits are preserved.

`make smoke` provisions and removes a test Pod for each enabled topology, checking
device count, cross-chip reduction, and XProf.

For a quick notebook check, confirm that `jax.local_device_count()` returns `4`.
