FROM node:22-bookworm-slim AS nodejs

FROM quay.io/jupyter/scipy-notebook:2024-11-11

USER root

# Install utilities needed by the Jupyter + TPU environment.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

USER ${NB_UID}

COPY docker/requirements.txt /tmp/requirements.txt

# Install python requirements
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The notebook base image includes JupyterLab but not Node/npm. Copy the
# official Node runtime so extension builds do not depend on Conda mirrors.
USER root
COPY --from=nodejs /usr/local/bin/node /usr/local/bin/node
COPY --from=nodejs /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
USER ${NB_UID}

# Build the small JupyterLab command used by the Stop TPU Server toolbar button.
# Its OAuth token can stop only the current user's server (see Hub values).
COPY --chown=${NB_UID}:${NB_GID} labextensions/stop-tpu-server /tmp/stop-tpu-server
RUN cd /tmp/stop-tpu-server && \
    npm ci --no-audit --no-fund && \
    npm run build && \
    mkdir -p /opt/conda/share/jupyter/labextensions/@course/stop-tpu-server && \
    cp -R labextension/. /opt/conda/share/jupyter/labextensions/@course/stop-tpu-server/ && \
    rm -rf /tmp/stop-tpu-server
