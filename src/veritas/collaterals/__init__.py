"""Attestation collateral for disconnected clusters."""

import argparse
import json
import logging
import shlex
import subprocess
import sys
from pathlib import Path

from veritas.collaterals import snp

log = logging.getLogger(__name__)

COCO_TOOLS_IMAGE = "quay.io/openshift_sandboxed_containers/coco-tools:0.5.1"
REQUEST_VERSION = 1

# Runs inside `oc debug node/...`, host filesystem mounted at /host.
PROBE = """\
if grep -qs Y /host/sys/module/kvm_amd/parameters/sev_snp; then
  echo tee=snp
  chroot /host podman run --rm --privileged {image} /tools/snphost show vcek-url
elif grep -qs Y /host/sys/module/kvm_intel/parameters/tdx; then
  echo tee=tdx
else
  echo tee=none
fi
"""


def oc(*args) -> str:
    result = subprocess.run(["oc", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"oc {' '.join(args)}\n{result.stderr}")
    return result.stdout


def list_nodes(selector: str) -> list[str]:
    out = oc("get", "nodes", "-l", selector, "-o", "name")
    return [line.removeprefix("node/") for line in out.split()]


def probe_node(node: str, image: str) -> dict | None:
    """Detect the node TEE and collect what it needs. None if no TEE."""
    out = oc("debug", f"node/{node}", "--", "sh", "-c",
             PROBE.format(image=shlex.quote(image)))
    lines = out.strip().splitlines()
    tee = next((l.removeprefix("tee=") for l in lines if l.startswith("tee=")), None)

    if tee == "snp":
        url = next((l for l in lines if l.startswith("https://")), None)
        if url is None:
            raise RuntimeError(f"{node}: snphost did not return a VCEK URL")
        return {"name": node, "tee": "snp", **snp.parse_vcek_url(url)}
    if tee == "tdx":
        return {"name": node, "tee": "tdx"}
    return None


def confirm(nodes: list[str], image: str) -> bool:
    server = oc("whoami", "--show-server").strip()
    print(f"""\
About to connect to cluster {server} and, on each node below, start a
privileged debug pod (oc debug) that runs {image}
to read the TEE identifiers. Nothing is changed on the cluster.

Nodes: {", ".join(nodes)}
""", file=sys.stderr)
    if not sys.stdin.isatty():
        raise RuntimeError("Not running interactively, pass --yes to continue")
    return input("Continue? [y/N] ").strip().lower() in ("y", "yes")


def is_azure(node: str) -> bool:
    return oc("get", "node", node, "-o", "jsonpath={.spec.providerID}").startswith("azure://")


def collect(nodes: list[str], image: str) -> dict:
    entries = []
    for node in nodes:
        if is_azure(node):
            log.info("%s: Azure node, recorded as TDX (SNP needs no collateral on Azure)", node)
            entries.append({"name": node, "tee": "tdx"})
            continue
        log.info("Probing node %s", node)
        entry = probe_node(node, image)
        if entry is None:
            log.warning("%s: no SNP or TDX support detected, skipping", node)
            continue
        log.info("%s: %s", node, entry["tee"])
        entries.append(entry)
    return {"version": REQUEST_VERSION, "nodes": entries}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="veritas collateral", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("collect", help="Read TEE identifiers from cluster nodes (read-only)")
    nodes = p.add_mutually_exclusive_group(required=True)
    nodes.add_argument("--node", action="append", dest="nodes", help="Node name (repeatable)")
    nodes.add_argument("--selector", help="Node label selector, e.g. node-role.kubernetes.io/worker=")
    p.add_argument("--image", default=COCO_TOOLS_IMAGE, help=f"coco-tools image (default: {COCO_TOOLS_IMAGE})")
    p.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    p.add_argument("-o", "--output", default="request.json", help="Output file (default: request.json)")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        names = args.nodes or list_nodes(args.selector)
        if not names:
            raise RuntimeError(f"No nodes match selector {args.selector}")
        if not args.yes and not confirm(names, args.image):
            log.info("Aborted")
            sys.exit(1)
        request = collect(names, args.image)
    except (RuntimeError, ValueError) as e:
        log.error("%s", e)
        sys.exit(1)

    Path(args.output).write_text(json.dumps(request, indent=2) + "\n")
    log.info("Written %s (%d nodes)", args.output, len(request["nodes"]))
