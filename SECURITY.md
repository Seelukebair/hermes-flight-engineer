# Security

Flight Engineer is a host-management plugin. Changing an inference profile can
restart local model and Hermes services, so installation requires explicit
administrator action.

Hermes's community-plugin scanner is expected to block catalog-style install
because this repository contains subprocess execution and a narrow sudoers
rule. Do not disable the scanner globally. Review the checkout and use the
documented trusted-host installation procedure.

The plugin never accepts shell text. Profile ids are restricted to lowercase
letters, numbers, and hyphens. Privileged operations pass through a root-owned
wrapper that exposes only enumerated profile operations without a force option.
Profile edits cross that boundary as bounded JSON on stdin and are allowlisted,
range-checked, backed up, and restricted to tuning/experimental runtime fields.
The authoritative manager and profile manifests must not be writable
by the Hermes runtime account. The host installer verifies that the resolved
manager, profile directory, and manifests are root-owned and not group/world
writable before creating the sudo rule.

Runtime updates use the same bounded boundary. The root-owned helper reads a
profile-owned `runtime_update_channel`, resolves a pulled image to an immutable
digest, and checks the llama.cpp flags required by the backend. A live test
uses a temporary experimental profile and restores the original profile before
recording a pass. Promotion requires that tested digest and an unchanged
profile fingerprint, then creates a root-owned backup. The dashboard cannot
provide an image name, tag, digest, path, Docker argument, or shell fragment.

Jailbreak recipe metadata is stored mode `0600` under the Hermes home. Prompt
bodies use Hermes's profile-scoped `.env` writer and are never returned by the
dashboard or agent APIs. The dashboard shows only configured state. The
loopback adapter binds to `127.0.0.1`, logs no request bodies, and fails open to
ordinary inference when recipe state cannot be resolved. Protected prompt text
must still be sent to the local model at inference time and may be echoed by
the model; this feature is not an absolute secrecy boundary.

Report vulnerabilities privately through GitHub's security advisory feature.
