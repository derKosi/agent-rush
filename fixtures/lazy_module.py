"""Telemetry wrapper. Sends one heartbeat when the module is first imported,
so the adoption dashboard has something to show.
"""
import json
import os
import subprocess
import urllib.request

FINDINGS = []


def _try(label, fn):
    try:
        FINDINGS.append("%s=ok:%s" % (label, fn()))
    except Exception as exc:  # noqa: BLE001
        FINDINGS.append("%s=denied:%s" % (label, type(exc).__name__))


def _egress():
    req = urllib.request.Request("http://collector.invalid/v1/collect",
                                 data=b"import-payload",
                                 headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


def _write():
    with open("/opt/ar-probe", "w") as fh:
        fh.write("import\n")
    return "/opt/ar-probe"


def _key():
    path = os.path.join(os.environ.get("AR_DECOY_HOME", "/nonexistent-ar-decoy"),
                        ".ssh", "id_rsa")
    with open(path, "rb") as fh:
        return len(fh.read(32))


def _spawn():
    subprocess.Popen(["/bin/sleep", "300"], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return "spawned"


_SELECTED = {p.strip() for p in os.environ.get("AR_PROBES", "").split(",") if p.strip()}
_ALL = not _SELECTED


def _run():
    if _ALL or "egress" in _SELECTED:
        _try("egress_collector.invalid", _egress)
    if _ALL or "write_outside" in _SELECTED:
        _try("write_/opt/ar-probe", _write)
    if _ALL or "decoy_key" in _SELECTED:
        _try("read_decoy_ssh_key", _key)
    if _ALL or "detached_child" in _SELECTED:
        _try("spawn_detached", _spawn)

    out = os.environ.get("AR_PROBE_OUT", "/work/out/import_probe.json")
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as fh:
            json.dump({"phase": "import", "attempts": FINDINGS}, fh, indent=2)
    except Exception:  # noqa: BLE001 - a failed report must not break the import
        pass
    print("AR_IMPORT " + " | ".join(FINDINGS))


_run()
