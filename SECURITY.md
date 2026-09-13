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
wrapper that exposes only profile activation and rollback without a force
option. The authoritative manager and profile manifests must not be writable
by the Hermes runtime account. The host installer verifies that the resolved
manager, profile directory, and manifests are root-owned and not group/world
writable before creating the sudo rule.

Report vulnerabilities privately through GitHub's security advisory feature.
