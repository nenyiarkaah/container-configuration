# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout: one branch per service

Each branch holds the config for a different homelab service and they share no code; `main` holds only a README. Don't merge branches into each other.

- `prometheus`: `prometheus.yml` and `rules/*.yml` (alert rules)
- `grafana`: dashboards JSON, provisioning, and `build.py`
- `prometheus-proxmox-ve-exporter`: `pve.yml`
- `traefik-load-balancer-configuration-*`: `traefik.yaml`, `dynamic.yaml`

Commit messages use the form `Feature:-...`, `Fix:-...`, `Refactor:-...`, `WIP:-...`.

## Prometheus branch

Validate before committing (`promtool` isn't installed locally; Docker works):

```sh
docker run --rm -v "$PWD":/c -w /c --entrypoint promtool prom/prometheus check config prometheus.yml
docker run --rm -v "$PWD":/c -w /c --entrypoint promtool prom/prometheus check rules rules/homelab.yml
```

Prometheus and Alertmanager run on the same LXC (`localhost:9090` and `:9093`). Alertmanager sends alerts to Slack `#homelab-alerts`. It's deployed from the separate **server-scripts** repo (`--tags alerting`).

Conventions and cross-repo dependencies:
- Every scrape target has a `host` label with the hostname (the hosts are named after Shakespeare characters). Alert summaries use `{{ $labels.host }}`, so new targets need the label too.
- The `pve` and `snmp` jobs follow the exporter pattern: the real target goes into `__param_target`/`instance`, and `__address__` is rewritten to the exporter. The PVE exporter runs at `10.140.50.145:9221`, and the SNMP exporter runs on juliet at `10.140.50.235:9116`. SNMP credentials live in the exporter, not in this repo.
- node_exporter (`:9100`), cAdvisor (`:9338`) and the SNMP exporter are installed on hosts by the Ansible `monitoring` role (`enable_cadvisor`, `enable_snmp_exporter`). Adding a target here assumes that role has already run on the host.
- Metrics such as `scheduled_container_*` and `backup_*` come from textfile output written by `run-scheduled-container.sh` and `run-backup.sh` in server-scripts. Rename them in both places.
- Hosts on the second network (ariel, belinda, desdemona, portia, perdita, ophelia) can't be reached from this Prometheus. Don't add them to the scrape jobs.
- Alert rules are commented with the past incident they would have caught. Keep doing that.
