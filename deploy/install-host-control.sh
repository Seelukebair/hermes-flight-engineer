#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
operator="${FLIGHT_ENGINEER_OPERATOR:-administrator}"

install -o root -g root -m 0755 \
  "$plugin_root/deploy/flight-engineer-control" \
  /usr/local/libexec/flight-engineer-control

cat >/etc/sudoers.d/hermes-flight-engineer <<EOF
${operator} ALL=(root) NOPASSWD: /usr/local/libexec/flight-engineer-control *
EOF
chmod 0440 /etc/sudoers.d/hermes-flight-engineer
visudo -cf /etc/sudoers.d/hermes-flight-engineer

echo "installed constrained Flight Engineer host control for ${operator}"

