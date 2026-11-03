#!/usr/bin/env bash
# Builds the sandbox image on the VM (and on a laptop if Docker is installed).
# No registry push: the image never leaves the machine that runs it.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${AR_IMAGE:-ar-sandbox:0.1}"

command -v docker >/dev/null 2>&1 || {
  echo "docker missing. On the VM: apt-get install -y docker.io && systemctl enable --now docker" >&2
  exit 2
}

echo "building $IMAGE from sandbox/"
docker build --pull -t "$IMAGE" sandbox/

echo
docker image inspect "$IMAGE" --format 'image: {{.RepoTags}} size={{.Size}}'
echo "entrypoint:"
docker image inspect "$IMAGE" --format '  {{json .Config.Entrypoint}}  user={{.Config.User}}'
