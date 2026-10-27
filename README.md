# container-configuration @ grafana

Provisioning for Grafana (LXC 113 on cordelia, `10.140.50.180:3000`).

| Path | Installed at |
|---|---|
| `provisioning/datasources/homelab.yaml` | `/etc/grafana/provisioning/datasources/` |
| `provisioning/dashboards/homelab.yaml` | `/etc/grafana/provisioning/dashboards/` |
| `dashboards/<Folder>/*.json` | `/var/lib/grafana/dashboards/homelab/<Folder>/` |

Edit `build.py` (or the files in `src/`), run `python3 build.py`, commit the output, then deploy with
`ansible-playbook -i inventory.yml site.yml --tags grafana` from server-scripts.
Provisioned dashboards are read-only in the UI: change them here.
