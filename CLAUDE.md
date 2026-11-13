# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout: one branch per service

Each branch holds the config for a different homelab service and they share no code; `main` holds only a README. Don't merge branches into each other.

- `prometheus`: `prometheus.yml` and `rules/*.yml` (alert rules)
- `grafana`: dashboards JSON, provisioning, and `build.py`
- `prometheus-proxmox-ve-exporter`: `pve.yml`
- `traefik-load-balancer-configuration-*`: `traefik.yaml`, `dynamic.yaml`

Commit messages use the form `Feature:-...`, `Fix:-...`, `Refactor:-...`, `WIP:-...`.

## Grafana branch

```sh
python3 build.py      # regenerates every file in dashboards/; stdlib only
git status -s         # a clean tree after a build means the output matches build.py
```

- **Never hand-edit `dashboards/*.json`.** Change `build.py` or `src/`, rebuild, then commit the source and the output together. Grafana reads only `dashboards/`, which is deployed from the separate **server-scripts** repo (`ansible-playbook -i inventory.yml site.yml --tags grafana`). The README lists the install paths.
- **Where each dashboard comes from:** the `BUILD` dict in `build.py` maps output paths to builder functions.
  - Overview, Containers and Rosalind are written in Python with the `stat`/`timeseries`/`table`/`query_var`/`dashboard` helpers.
  - Hosts is grafana.com dashboard 1860 (`src/node-exporter-full-*.json`).
  - Proxmox and Prometheus are UI exports in `src/`. They're patched after loading, so put fixes in their builder functions, not in the JSON in `src/`.
- **Folders come from the subdirectory names** under `dashboards/` (`foldersFromFilesStructure`). Provisioned dashboards are read-only in the Grafana UI (`editable: False`, `allowUiUpdates: false`).
- **Every panel uses the provisioned datasource** `DS = prometheus-direct` (`http://10.140.50.125:9090`). This bypasses the `*.safetypin.me.uk` proxy. For imported dashboards, `point_at_direct()` rewrites their datasource references.
- **Dashboards depend on the `prometheus` branch:** they use its `host` label, the job names, and metric names from server-scripts such as `scheduled_container_*`. Panel descriptions also name the alerts in `rules/homelab.yml` and their thresholds. If a rule changes there, update the matching description here.
- **Grafana itself** is LXC 113 on cordelia at `10.140.50.180:3000`.
