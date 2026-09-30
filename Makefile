# shared-tpu-notebooks: direct TPU notebooks for LLM Systems
-include config.env

PROJECT ?=
REGION ?= us-west4
CLUSTER ?= tpu-notebooks
NAMESPACE ?= llmsys
MAX_TPU_NOTEBOOKS ?= 20
DOMAIN ?=
STUDENT_GROUP ?=
TA_GROUP ?=
ADMIN_USERS ?=
TEST_ACCOUNTS ?=

export PROJECT REGION CLUSTER NAMESPACE MAX_TPU_NOTEBOOKS DOMAIN STUDENT_GROUP TA_GROUP ADMIN_USERS TEST_ACCOUNTS

.PHONY: check preflight image cluster hub smoke iap demo expand-pvcs expand-pvcs-dry-run clean-pvcs clean-pvcs-dry-run teardown help

check:
ifndef PROJECT
	$(error PROJECT is not set. Set it in config.env or run: make $(MAKECMDGOALS) PROJECT=my-gcp-project)
endif

preflight: check
	bash scripts/00_preflight.sh

image: check
	bash scripts/01_build_image.sh

cluster: check
	bash scripts/02_create_cluster.sh

hub: check
	bash scripts/03_deploy_hub.sh

# Runs JAX in a short-lived Pod with the same image, TPU, and sandbox settings
# as the student notebook. Complete the browser check described in the guide too.
smoke: check
	bash scripts/04_smoke_tpu_notebook.sh

iap: check
	bash scripts/08_setup_iap.sh

demo: image cluster hub smoke
	@echo "Secure the hub with: make iap"

expand-pvcs-dry-run: check
	bash scripts/11_expand_pvcs.sh --dry-run

expand-pvcs: check
	bash scripts/11_expand_pvcs.sh --execute

clean-pvcs-dry-run: check
	bash scripts/10_cleanup_pvcs.sh --dry-run

clean-pvcs: check
	bash scripts/10_cleanup_pvcs.sh --execute

teardown: check
	bash scripts/99_teardown.sh

help:
	@echo "Direct TPU notebook commands:"
	@echo "  make preflight      Check regional v5e quota and availability"
	@echo "  make image          Build and push the Jupyter + JAX TPU image"
	@echo "  make cluster        Create Autopilot cluster, namespace, storage, and TPU quota"
	@echo "  make hub            Deploy JupyterHub for students and TAs"
	@echo "  make smoke          Run a TPU smoke Pod with the notebook image"
	@echo "  make iap            Configure HTTPS and Google Identity-Aware Proxy"
	@echo "  make clean-pvcs-dry-run / clean-pvcs   Preview or remove home disks"
	@echo "  make teardown       Delete the cluster and static IP"
