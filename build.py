#!/usr/bin/env python3
"""Build the provisioned Grafana dashboards into dashboards/<folder>/.

Run `python3 build.py` after editing, and commit both this file and the output.
Grafana's file provider reads dashboards/; it never sees src/ or this script.

- Overview, Containers and Rosalind are defined here.
- Hosts is grafana.com 1860 (Node Exporter Full), from src/.
- Proxmox and Prometheus are the dashboards first built in the Grafana UI,
  exported to src/ on 2026-10-27, with their bugs fixed below.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus-direct"}


# ---------------------------------------------------------------- helpers

def target(expr, legend="", instant=False, ref="A", fmt=None):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t.update(instant=True, range=False)
    if fmt:
        t["format"] = fmt
    return t


def panel(kind, title, targets, x, y, w, h, unit=None, description=None, **extra):
    p = {
        "type": kind,
        "title": title,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {},
    }
    if unit:
        p["fieldConfig"]["defaults"]["unit"] = unit
    if description:
        p["description"] = description
    p.update(extra)
    return p


def stat(title, expr, x, y, w=4, h=4, unit=None, steps=None, legend="", mappings=None, description=None):
    p = panel("stat", title, [target(expr, legend, instant=True)], x, y, w, h, unit, description)
    p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "none"}
    p["fieldConfig"]["defaults"]["thresholds"] = {
        "mode": "absolute",
        "steps": steps or [{"color": "green", "value": None}],
    }
    if mappings:
        p["fieldConfig"]["defaults"]["mappings"] = mappings
    return p


def timeseries(title, targets, x, y, w=12, h=8, unit=None, description=None, stack=False):
    p = panel("timeseries", title, targets, x, y, w, h, unit, description)
    p["fieldConfig"]["defaults"]["custom"] = {
        "fillOpacity": 10,
        "showPoints": "never",
        "stacking": {"mode": "normal" if stack else "none"},
    }
    p["options"] = {
        "legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "max"]},
        "tooltip": {"mode": "multi", "sort": "desc"},
    }
    return p


def table(title, targets, x, y, w, h, transformations, overrides=None, description=None):
    p = panel("table", title, targets, x, y, w, h, description=description)
    p["transformations"] = transformations
    p["fieldConfig"]["overrides"] = overrides or []
    p["options"] = {"showHeader": True, "cellHeight": "sm"}
    return p


def query_var(name, query, label=None, multi=True, include_all=True):
    return {
        "name": name,
        "label": label or name,
        "type": "query",
        "datasource": DS,
        "query": {"query": query, "refId": f"{name}-var"},
        "definition": query,
        "refresh": 2,
        "sort": 1,
        "multi": multi,
        "includeAll": include_all,
        "current": {"text": "All", "value": "$__all"} if include_all else {},
    }


def dashboard(uid, title, panels, tags, variables=(), refresh="1m", time_from="now-6h"):
    for i, p in enumerate(panels, 1):
        p["id"] = i
    return {
        "uid": uid,
        "title": title,
        "tags": ["homelab"] + tags,
        "timezone": "browser",
        "schemaVersion": 41,
        "editable": False,
        "refresh": refresh,
        "time": {"from": time_from, "to": "now"},
        "templating": {"list": list(variables)},
        "annotations": {"list": []},
        "panels": panels,
    }


RED_IF_ABOVE_ZERO = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
UP_DOWN = [{"type": "value", "options": {
    "0": {"text": "DOWN", "color": "red"},
    "1": {"text": "UP", "color": "green"},
}}]


# ---------------------------------------------------------------- overview

def overview():
    hosts_by = 'host'
    panels = [
        stat("Targets up", "sum(up)", 0, 0),
        stat("Targets down", "count(up == 0) or vector(0)", 4, 0, steps=RED_IF_ABOVE_ZERO),
        stat("Alerts firing", 'count(ALERTS{alertstate="firing"}) or vector(0)', 8, 0,
             steps=RED_IF_ABOVE_ZERO,
             description="Prometheus alert rules (container-configuration @ prometheus, rules/homelab.yml). "
                         "No notification channel is configured yet: this panel is the only place they show."),
        stat("Last importer exit code", 'scheduled_container_last_exit_code{name="national-lottery-importer"}',
             12, 0, steps=RED_IF_ABOVE_ZERO,
             description="Written by run-scheduled-container.sh on juliet after each 06:00 UTC run."),
        stat("Hours since importer ran",
             '(time() - scheduled_container_last_run_timestamp_seconds{name="national-lottery-importer"}) / 3600',
             16, 0, unit="h",
             steps=[{"color": "green", "value": None}, {"color": "orange", "value": 25}, {"color": "red", "value": 26}]),
        stat("Containers running", 'count(container_last_seen{name!=""})', 20, 0),

        table("Hosts", [
            target('100 * (1 - avg by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])))', instant=True, ref="CPU", fmt="table"),
            target('100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)', instant=True, ref="Memory", fmt="table"),
            target('100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})', instant=True, ref="Disk", fmt="table"),
            target('node_load1', instant=True, ref="Load", fmt="table"),
            target('time() - node_boot_time_seconds', instant=True, ref="Uptime", fmt="table"),
            target('count by (host) (container_last_seen{name!=""})', instant=True, ref="Containers", fmt="table"),
        ], 0, 4, 14, 9, [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "instance": True, "job": True, "__name__": True},
                "indexByName": {"host": 0, "Value #CPU": 1, "Value #Memory": 2, "Value #Disk": 3,
                                "Value #Load": 4, "Value #Containers": 5, "Value #Uptime": 6},
                "renameByName": {"host": "Host", "Value #CPU": "CPU %", "Value #Memory": "Memory used %",
                                 "Value #Disk": "Root disk used %", "Value #Load": "Load (1m)",
                                 "Value #Containers": "Containers", "Value #Uptime": "Uptime"},
            }},
        ], overrides=[
            {"matcher": {"id": "byRegexp", "options": "CPU %|Memory used %|Root disk used %"}, "properties": [
                {"id": "unit", "value": "percent"}, {"id": "decimals", "value": 0},
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
                {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                    {"color": "green", "value": None}, {"color": "orange", "value": 80}, {"color": "red", "value": 90}]}},
            ]},
            {"matcher": {"id": "byName", "options": "Uptime"}, "properties": [{"id": "unit", "value": "s"}]},
        ], description="Hosts this Prometheus can reach. The second network (ariel, belinda, desdemona, portia, perdita, ophelia) is not scraped yet."),

        table("Scrape targets", [target("up", instant=True, fmt="table")], 14, 4, 10, 9, [
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "__name__": True},
                "indexByName": {"host": 0, "job": 1, "instance": 2, "Value": 3},
                "renameByName": {"host": "Host", "job": "Job", "instance": "Target", "Value": "State"},
            }},
            {"id": "sortBy", "options": {"sort": [{"field": "State"}]}},
        ], overrides=[{"matcher": {"id": "byName", "options": "State"}, "properties": [
            {"id": "mappings", "value": UP_DOWN},
            {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
        ]}]),

        table("Alerts", [target('ALERTS', instant=True, fmt="table")], 0, 13, 24, 5, [
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "__name__": True, "Value": True},
                "renameByName": {"alertname": "Alert", "alertstate": "State"},
            }},
        ], description="Pending and firing alerts. Empty means all clear."),

        timeseries("CPU busy by host", [target(
            '100 * (1 - avg by (host) (rate(node_cpu_seconds_total{mode="idle"}[$__rate_interval])))', "{{host}}")],
            0, 18, unit="percent"),
        timeseries("Memory available by host", [target(
            '100 * node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes', "{{host}}")],
            12, 18, unit="percent",
            description="NodeMemoryAvailableLow fires below 10% for 15 minutes."),
        timeseries("Top 10 containers by memory", [target(
            'topk(10, container_memory_working_set_bytes{name!=""})', "{{name}} ({{host}})")],
            0, 26, unit="bytes"),
        timeseries("Top 10 containers by CPU", [target(
            'topk(10, sum by (host, name) (rate(container_cpu_usage_seconds_total{name!=""}[$__rate_interval])))',
            "{{name}} ({{host}})")],
            12, 26, unit="short", description="CPU cores used."),
    ]
    return dashboard("homelab-overview", "Homelab Overview", panels, ["overview"])


# ---------------------------------------------------------------- containers

def containers():
    sel = 'name!="", host=~"$host", name=~"$container"'
    panels = [
        table("Containers", [
            target(f'container_last_seen{{{sel}}}', instant=True, ref="Seen", fmt="table"),
            target(f'time() - container_start_time_seconds{{{sel}}}', instant=True, ref="Up", fmt="table"),
        ], 0, 0, 24, 8, [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "__name__": True, "id": True, "instance": True, "job": True,
                                  "Value #Seen": True},
                "indexByName": {"host": 0, "name": 1, "container_label_com_docker_compose_project": 2,
                                "image": 3, "Value #Up": 4},
                "renameByName": {"host": "Host", "name": "Container",
                                 "container_label_com_docker_compose_project": "Compose project",
                                 "container_label_com_docker_compose_service": "Service",
                                 "image": "Image", "Value #Up": "Up for"},
            }},
        ], overrides=[{"matcher": {"id": "byName", "options": "Up for"}, "properties": [{"id": "unit", "value": "s"}]}]),
        timeseries("CPU", [target(
            f'sum by (host, name) (rate(container_cpu_usage_seconds_total{{{sel}}}[$__rate_interval]))',
            "{{name}} ({{host}})")], 0, 8, unit="short", description="CPU cores used."),
        timeseries("Memory (working set)", [target(
            f'container_memory_working_set_bytes{{{sel}}}', "{{name}} ({{host}})")], 12, 8, unit="bytes"),
        timeseries("Network received", [target(
            f'sum by (host, name) (rate(container_network_receive_bytes_total{{{sel}}}[$__rate_interval]))',
            "{{name}} ({{host}})")], 0, 16, unit="Bps"),
        timeseries("Network sent", [target(
            f'sum by (host, name) (rate(container_network_transmit_bytes_total{{{sel}}}[$__rate_interval]))',
            "{{name}} ({{host}})")], 12, 16, unit="Bps"),
        timeseries("Disk read", [target(
            f'sum by (host, name) (rate(container_fs_reads_bytes_total{{{sel}}}[$__rate_interval]))',
            "{{name}} ({{host}})")], 0, 24, unit="Bps"),
        timeseries("Disk written", [target(
            f'sum by (host, name) (rate(container_fs_writes_bytes_total{{{sel}}}[$__rate_interval]))',
            "{{name}} ({{host}})")], 12, 24, unit="Bps"),
    ]
    variables = [
        query_var("host", 'label_values(container_last_seen, host)', "Host"),
        query_var("container", 'label_values(container_last_seen{host=~"$host", name!=""}, name)', "Container"),
    ]
    return dashboard("homelab-containers", "Containers", panels, ["containers", "cadvisor"], variables)


# ---------------------------------------------------------------- rosalind

NORMAL_OR_FAILED = [{"type": "value", "options": {"1": {"text": "Normal", "color": "green"}}},
                    {"type": "range", "options": {"from": 2, "to": 99, "result": {"text": "Failed", "color": "red"}}}]
RAID_STATUS = [{"type": "value", "options": {
    "1": {"text": "Normal", "color": "green"},
    "2": {"text": "Repairing", "color": "orange"},
    "3": {"text": "Migrating", "color": "orange"},
    "4": {"text": "Expanding", "color": "orange"},
    "11": {"text": "Degraded", "color": "red"},
    "12": {"text": "Crashed", "color": "red"},
}}]
NORMAL_ONLY = [{"color": "green", "value": None}, {"color": "red", "value": 2}]


def rosalind():
    """Synology DS (Rosalind) over SNMPv3: the snmp job, through the exporter on juliet."""
    vol = 'raidName=~"Volume.*"'
    panels = [
        stat("System", "systemStatus", 0, 0, steps=NORMAL_ONLY, mappings=NORMAL_OR_FAILED),
        stat("Power", "powerStatus", 4, 0, steps=NORMAL_ONLY, mappings=NORMAL_OR_FAILED),
        stat("Fans", "max(systemFanStatus or cpuFanStatus)", 8, 0, steps=NORMAL_ONLY, mappings=NORMAL_OR_FAILED),
        stat("RAID", "max(raidStatus)", 12, 0, steps=NORMAL_ONLY, mappings=RAID_STATUS,
             description="Worst status across the storage pool and volume."),
        stat("Volume 1 free", f'100 * raidFreeSize{{{vol}}} / raidTotalSize', 16, 0, unit="percent",
             steps=[{"color": "red", "value": None}, {"color": "orange", "value": 10}, {"color": "green", "value": 20}]),
        stat("System temperature", "temperature", 20, 0, unit="celsius",
             steps=[{"color": "green", "value": None}, {"color": "orange", "value": 65}, {"color": "red", "value": 75}]),

        table("Disks", [
            target('diskModel', instant=True, ref="Model", fmt="table"),
            target('diskTemperature', instant=True, ref="Temp", fmt="table"),
            target('diskStatus', instant=True, ref="Status", fmt="table"),
            target('diskHealthStatus', instant=True, ref="Health", fmt="table"),
            target('diskBadSector', instant=True, ref="Bad", fmt="table"),
            target('diskRemainLife', instant=True, ref="Life", fmt="table"),
        ], 0, 4, 24, 7, [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "host": True, "instance": True, "job": True, "Value #Model": True},
                "indexByName": {"diskID": 0, "diskModel": 1, "Value #Temp": 2, "Value #Status": 3,
                                "Value #Health": 4, "Value #Bad": 5, "Value #Life": 6},
                "renameByName": {"diskID": "Disk", "diskModel": "Model", "Value #Temp": "Temperature",
                                 "Value #Status": "Status", "Value #Health": "Health",
                                 "Value #Bad": "Bad sectors", "Value #Life": "SSD life left %"},
            }},
        ], overrides=[
            {"matcher": {"id": "byRegexp", "options": "Status|Health"}, "properties": [
                {"id": "mappings", "value": NORMAL_OR_FAILED},
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
            ]},
            {"matcher": {"id": "byName", "options": "Temperature"}, "properties": [
                {"id": "unit", "value": "celsius"},
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
                {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                    {"color": "green", "value": None}, {"color": "orange", "value": 50}, {"color": "red", "value": 55}]}},
            ]},
            {"matcher": {"id": "byName", "options": "SSD life left %"}, "properties": [
                {"id": "mappings", "value": [{"type": "value", "options": {"-1": {"text": "-"}}}]},
            ]},
        ], description="RosalindDiskUnhealthy fires if Status or Health leaves Normal; RosalindDiskHot above 55 C for 30 minutes."),

        timeseries("CPU and memory", [
            target("cpuUtilization", "CPU"),
            target("memUtilization", "Memory", ref="B"),
        ], 0, 11, unit="percent"),
        timeseries("Volume used", [target(
            f'100 * (1 - raidFreeSize{{{vol}}} / raidTotalSize)', "{{raidName}}")], 12, 11, unit="percent",
            description="RosalindVolumeAlmostFull fires below 10% free."),
        timeseries("Disk temperatures", [target("diskTemperature", "{{diskID}}")], 0, 19, unit="celsius"),
        timeseries("Disk throughput", [
            target('rate(storageIONReadX[$__rate_interval])', "{{storageIODevice}} read"),
            target('-rate(storageIONWrittenX[$__rate_interval])', "{{storageIODevice}} write", ref="B"),
        ], 12, 19, unit="Bps", description="Writes are drawn below zero."),
        timeseries("Network", [
            target('rate(ifHCInOctets{ifName=~"eth.*|bond.*"}[$__rate_interval]) * 8', "{{ifName}} in"),
            target('-rate(ifHCOutOctets{ifName=~"eth.*|bond.*"}[$__rate_interval]) * 8', "{{ifName}} out", ref="B"),
        ], 0, 27, 24, unit="bps", description="Physical ports and the bond. Out is drawn below zero."),
    ]
    return dashboard("homelab-rosalind", "Rosalind (NAS)", panels, ["rosalind", "synology", "snmp"])


# ---------------------------------------------------------------- imported / exported

def point_at_direct(d):
    """Swap every Prometheus datasource reference for the provisioned direct one."""
    s = json.dumps(d)
    s = re.sub(r'\{"type": "prometheus", "uid": "[^"]*"\}', json.dumps(DS), s)
    s = s.replace('"datasource": "prometheus"', '"datasource": ' + json.dumps(DS))
    d = json.loads(s)
    d.pop("id", None)
    d.pop("version", None)
    d["tags"] = sorted(set(["homelab"] + d.get("tags", [])))
    d["editable"] = False
    return d


def hosts():
    d = json.loads((ROOT / "src/node-exporter-full-1860-rev45.json").read_text())
    for v in d["templating"]["list"]:
        if v["name"] == "ds_prometheus":
            v["current"] = {"text": "Prometheus (direct)", "value": "prometheus-direct"}
            v["hide"] = 2
    d["uid"] = "homelab-hosts"
    d["title"] = "Hosts (Node Exporter Full)"
    d.pop("id", None)
    d["tags"] = sorted(set(["homelab"] + d.get("tags", [])))
    return d


def proxmox():
    d = point_at_direct(json.loads((ROOT / "src/proxmox-ui-export.json").read_text()))
    d["uid"] = "homelab-proxmox"
    d["title"] = "Proxmox"
    for p in d["panels"]:
        exprs = [t.get("expr", "") for t in p.get("targets", [])]
        if p.get("title") == "Disk IO/s":
            # Read side was missing the instance filter
            for t in p["targets"]:
                t["expr"] = t["expr"].replace("rate(pve_disk_read_bytes[5m])",
                                              'rate(pve_disk_read_bytes{instance="$instance"}[5m])')
        elif not p.get("title") and exprs and exprs[0].startswith("pve_cpu_usage_limit"):
            p["title"] = "Node CPUs"
            p["targets"][0]["expr"] = 'pve_cpu_usage_limit{instance="$instance"} and on(id) pve_node_info'
        elif not p.get("title") and exprs and exprs[0].startswith("pve_memory_usage_bytes"):
            p["title"] = "Node memory"
    return d


def prometheus():
    d = point_at_direct(json.loads((ROOT / "src/prometheus-stats-ui-export.json").read_text()))
    d["uid"] = "homelab-prometheus"
    d["title"] = "Prometheus"
    return d


BUILD = {
    "Overview/homelab-overview.json": overview,
    "Containers/containers.json": containers,
    "Infrastructure/hosts.json": hosts,
    "Infrastructure/proxmox.json": proxmox,
    "Infrastructure/rosalind.json": rosalind,
    "Meta/prometheus.json": prometheus,
}

if __name__ == "__main__":
    for path, build in BUILD.items():
        out = OUT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(build(), indent=2) + "\n")
        print("wrote", out.relative_to(ROOT))
