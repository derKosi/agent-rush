"""Second pass: import the installed package and see what it does.

The build hook is only one place a payload can hide. The common real evasion is a clean
build and a hostile first import, so this runs inside the same sandbox, after install,
with the same probes and the same limits.

It cannot ask the package which modules it has, because that would import it early.
It reads the distribution metadata instead and imports each top-level module on
purpose, so the moment is deliberate and logged.
"""

import importlib
import importlib.metadata as md
import json

BASE = "/usr/local/share/base_dists.txt"


def base_names():
    try:
        with open(BASE, encoding="utf-8") as fh:
            return {line.strip() for line in fh if line.strip()}
    except OSError:
        return set()


def top_level(dist):
    try:
        text = dist.read_text("top_level.txt")
        if text:
            return [line.strip() for line in text.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001
        pass
    mods = set()
    for path in dist.files or []:
        parts = str(path).split("/")
        if not parts:
            continue
        head = parts[0]
        if head.endswith((".dist-info", ".egg-info", ".data")):
            continue
        if head == "__pycache__":
            continue
        if head.endswith(".py"):
            head = head[:-3]
        mods.add(head)
    return sorted(mods)


def main():
    known = base_names()
    installed = [d for d in md.distributions() if (d.metadata["Name"] or "") not in known]
    report = {"distributions": [], "imports": []}

    for dist in installed:
        name = dist.metadata["Name"]
        modules = top_level(dist)
        report["distributions"].append({"name": name, "modules": modules})
        for module in modules:
            entry = {"module": module, "ok": False}
            try:
                importlib.import_module(module)
                entry["ok"] = True
            except BaseException as exc:  # noqa: BLE001 - the payload may raise anything
                entry["error"] = f"{type(exc).__name__}: {exc}"
            report["imports"].append(entry)

    print("AR_IMPORT_RESULT " + json.dumps(report))


if __name__ == "__main__":
    main()
