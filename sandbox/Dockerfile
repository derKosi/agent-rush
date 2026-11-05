# Sandbox image for untrusted package triage.
#
# Threat model: the build hook in the package is hostile. Assume it reads every
# environment variable, walks the filesystem and tries to phone home on first line.
# Therefore: no credentials in this image, no network capability by default,
# no root, no writable root filesystem (enforced by run.sh, not here).

FROM python:3.12-slim

# Fixed uid so the host can reason about ownership of the mounted work dir.
RUN groupadd -g 10001 sandbox \
 && useradd -u 10001 -g 10001 -m -d /home/sandbox -s /usr/sbin/nologin sandbox \
 && mkdir -p /work/out \
 && chown -R 10001:10001 /work

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp/home

# A build backend has to exist for `pip install --no-build-isolation` to run a
# setup.py sdist at all. python:3.12-slim ships pip without setuptools, so the
# fixture would fail with BackendUnavailable and we would learn nothing.
# Unpinned on purpose: this image is throwaway per task, not a build cache.
RUN pip install --no-cache-dir setuptools wheel

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY import_pass.py /usr/local/bin/import_pass.py
RUN chmod 0555 /usr/local/bin/entrypoint.sh /usr/local/bin/import_pass.py \
 && python3 -c "import importlib.metadata as m; print(chr(10).join(sorted(d.metadata['Name'] or '' for d in m.distributions())))" \
    > /usr/local/share/base_dists.txt

USER 10001:10001
WORKDIR /work

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
