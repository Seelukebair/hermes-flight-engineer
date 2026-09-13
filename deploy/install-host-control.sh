#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
operator="${FLIGHT_ENGINEER_OPERATOR:-administrator}"
manager="$(readlink -f "${FLIGHT_ENGINEER_MANAGER:-/usr/local/bin/jarvis-model-profile}")"
profile_dir="$(readlink -f "${FLIGHT_ENGINEER_PROFILE_DIR:-/srv/gemma4-production/profiles}")"

for path in "$manager" "$profile_dir"; do
  if [[ ! -e "$path" || "$(stat -c '%U' "$path")" != "root" ]]; then
    echo "refusing install: $path must exist and be root-owned" >&2
    exit 1
  fi
  if find "$path" -maxdepth 0 -perm /022 -print -quit | grep -q .; then
    echo "refusing install: $path must not be group/world writable" >&2
    exit 1
  fi
done

if find "$profile_dir" -maxdepth 1 -type f -name '*.json' -perm /022 -print -quit | grep -q .; then
  echo "refusing install: profile manifests must not be group/world writable" >&2
  exit 1
fi

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 \
  "$plugin_root/deploy/flight-engineer-control" \
  /usr/local/libexec/flight-engineer-control

cat >/etc/sudoers.d/hermes-flight-engineer <<EOF
${operator} ALL=(root) NOPASSWD: /usr/local/libexec/flight-engineer-control *
EOF
chmod 0440 /etc/sudoers.d/hermes-flight-engineer
visudo -cf /etc/sudoers.d/hermes-flight-engineer

echo "installed constrained Flight Engineer host control for ${operator}"
