# GX-10 operator targets. Sequencing only: every step lives in a tested script
# or a systemd unit. Run on the GX-10 host as root:
#
#   sudo make -C /opt/aca/deploy/gx10 <target>
#
# Never pulls: a pull that changes bind-mounted files without recreating the
# containers is a silent outage, so `git pull` stays an explicit operator step.

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

ROOT ?= /opt/aca
PROJECT ?= aca-gx10
IMAGE ?= ghcr.io/jankneumann/agentic-content-analyzer
SINCE ?= 30 minutes ago
STOP_TIMEOUT ?= 15
UNIT_DIR ?= /etc/systemd/system
IMAGES_ENV ?= /etc/aca/gx10-images.env
SHA := $(shell git -C $(ROOT) rev-parse --short HEAD 2>/dev/null)

SCRIPTS := $(ROOT)/scripts/gx10
UNITS := $(wildcard $(ROOT)/deploy/gx10/systemd/*.service $(ROOT)/deploy/gx10/systemd/*.timer)
GX10_UNITS := aca-gx10-image-pins aca-gx10-openbao-container aca-gx10-openbao-provision \
  aca-gx10-secrets aca-gx10-proxy-policy aca-gx10-firewall aca-gx10-maintenance-plans aca-gx10

.PHONY: help require-root install ownership preflight provision secrets image image-pins \
  start stop status logs verify

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | sort

require-root:
	@[[ "$$(id -u)" == 0 ]] || { echo "run as root: sudo make -C $(ROOT)/deploy/gx10 <target>" >&2; exit 1; }

install: require-root ## Install reviewed units and timers, verify them, daemon-reload
	install -m 0644 $(UNITS) $(UNIT_DIR)/
	systemd-analyze verify $(UNIT_DIR)/aca-gx10*.service $(UNIT_DIR)/aca-gx10*.timer
	systemctl daemon-reload

# The uid:gid values are the image users from docs/GX10_PODMAN_SETUP.md; a
# deployment test cross-checks them against the compose `user:` entries.
ownership: require-root ## Apply data-directory ownership, then run the preflight
	install -d -o root -g root -m 0700 /srv/aca/application /srv/aca/caddy-data /srv/aca/caddy-config
	install -d -o 999 -g 999 -m 0700 /srv/aca/postgres /srv/aca/langfuse-postgres /srv/aca/falkordb
	install -d -o 999 -g 1000 -m 0700 /srv/aca/redis
	install -d -o 101 -g 101 -m 0700 /srv/aca/clickhouse /srv/aca/clickhouse-logs
	install -d -o 60001 -g 60001 -m 0700 /srv/aca/minio
	install -d -o 100 -g 1000 -m 0700 /srv/aca/openbao
	install -d -o 13 -g 13 -m 0700 /srv/aca/squid-logs
	$(MAKE) preflight

preflight: require-root ## Fail closed unless every bind mount is owned by its container user
	$(SCRIPTS)/check_persistence_ownership.py --compose $(ROOT)/docker-compose.gx10.yml

provision: require-root ## Run the explicit first-install OpenBao ceremony (idempotent)
	systemctl start aca-gx10-openbao-provision.service
	test -s /etc/aca/gx10/openbao-provisioned.ready
	@echo "provisioned"

secrets: require-root install ## Ensure OpenBao runs, then re-render runtime secrets
	systemctl restart aca-gx10-openbao-container.service
	systemctl restart aca-gx10-secrets.service

image: require-root ## Build gx10-<sha> from the checked-out commit, push, print the pin line
	@[[ -z "$$(git -C $(ROOT) status --porcelain)" ]] || { echo "worktree is dirty; the image must match commit $(SHA)" >&2; exit 1; }
	cd $(ROOT) && podman build -t $(IMAGE):gx10-$(SHA) .
	podman push $(IMAGE):gx10-$(SHA)
	@digest="$$(skopeo inspect --format '{{.Digest}}' docker://$(IMAGE):gx10-$(SHA))"; \
	  echo; echo "pin this in $(IMAGES_ENV), then: make image-pins"; \
	  echo "GX10_APP_IMAGE=$(IMAGE):gx10-$(SHA)@$$digest"

image-pins: require-root ## Re-run the registry provenance gate after editing the images file
	systemctl restart aca-gx10-image-pins.service

start: require-root install ## Install units, remove every project container, start the runtime
	podman ps -aq --filter label=io.podman.compose.project=$(PROJECT) | xargs -r podman rm -f --depend -t $(STOP_TIMEOUT)
	systemctl reset-failed 'aca-gx10*'
	systemctl start aca-gx10.service
	$(MAKE) status

stop: require-root ## Stop the runtime; its ExecStop sweeps the containers
	systemctl stop aca-gx10.service

status: ## Unit states and containers on one screen
	@for unit in $(GX10_UNITS); do printf '%-32s ' "$$unit"; systemctl show "$$unit.service" -p ActiveState,SubState,Result --value | paste -sd' '; done
	@podman ps -a --filter label=io.podman.compose.project=$(PROJECT) --format 'table {{.Names}}\t{{.Status}}'

logs: ## Failures across every gx10 unit since $(SINCE), noise removed
	@journalctl --since "$(SINCE)" --no-pager -o short -u 'aca-gx10*' \
	  | grep -vE 'Copying blob|skipping:|\[.podman|podman-compose.sh\[[0-9]+\]: \[|Processing:' \
	  | grep -iE 'fatal|error|denied|mismatch|did not become healthy|Failed|preflight|Traceback' \
	  | grep -v RuntimeWarning | tail -40 || true

verify: require-root ## Run the live clean-stack gate (needs the image variables exported)
	$(SCRIPTS)/verify_clean_stack.sh
