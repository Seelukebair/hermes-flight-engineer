# Hermes Flight Engineer

Flight Engineer gives Hermes self-awareness and guarded control of validated
local inference backend configurations. Hermes remains the pilot: native model
selection, fallbacks, delegation, auxiliary tasks, and Mixture of Agents stay
owned by Hermes.

Flight Engineer manages the machinery behind one stable Hermes route:

```text
gemma4-thinker-local/gemma4-thinker
```

Switching a profile changes the tested backend configuration serving that
route. It does not present mutually exclusive single-GPU profiles as
simultaneously loaded models.

## Surfaces

- `flight_engineer` agent tool: status, list, guarded use, and rollback.
- `hermes flight-engineer`: the same operations for operators.
- `flight-engineer` skill: teaches Hermes the safety and native MoA boundary.
- Dashboard tab: current route, service state, profile inventory, and confirmed
  switching, with a link to Hermes's native MoA settings.
- Root-owned control wrapper: permits only `use PROFILE_ID` and `rollback`; no
  arbitrary shell, runtime arguments, paths, force switch, or service names.

## Current Driver Contract

Version 0.1 targets the JSON status and profile-manifest contract provided by
`/usr/local/bin/jarvis-model-profile`. Paths can be overridden with:

```text
FLIGHT_ENGINEER_MANAGER
FLIGHT_ENGINEER_CONTROL
FLIGHT_ENGINEER_PROFILE_DIR
```

The next driver boundary will make the host manager backend-neutral while
retaining the same plugin API. llama.cpp is the first implementation; Ollama,
vLLM, and other runtimes should be adapters, not conditionals in the Hermes
plugin.

Tracked runtime investigations, including DwarfStar (`ds4`), live in
[ROADMAP.md](ROADMAP.md).

## Trusted Host Install

Flight Engineer intentionally controls a root-owned inference service. Hermes's
community-plugin scanner therefore classifies it as dangerous and blocks
`hermes plugins install`; that is the correct default for an arbitrary plugin
from the internet. Do not disable `plugins.scan_on_install` globally.

After reviewing the checkout, install it explicitly as a trusted local plugin:

```bash
git clone https://github.com/Seelukebair/hermes-flight-engineer.git \
  ~/.hermes/plugins/flight-engineer
sudo FLIGHT_ENGINEER_OPERATOR="$USER" \
  bash ~/.hermes/plugins/flight-engineer/deploy/install-host-control.sh
hermes plugins doctor ~/.hermes/plugins/flight-engineer --ci
hermes plugins compat ~/.hermes/plugins/flight-engineer
hermes plugins enable flight-engineer
```

The host installer is intentionally separate from plugin registration. It
installs a root-owned wrapper and one narrow sudoers rule. The wrapper accepts
only `use PROFILE_ID` and `rollback`, validates the profile identifier, and
cannot forward force flags or arbitrary arguments. Profile manifests and the
underlying manager must also remain root-owned.

Restart the dashboard once to mount `plugin_api.py`; a normal dashboard plugin
rescan is sufficient for later frontend-only changes.

## Mixture Of Agents

Use Hermes's native Models settings or `hermes moa configure`. Add
`gemma4-thinker-local/gemma4-thinker` as a reference or aggregator when the
active local profile is suitable. Flight Engineer does not edit or duplicate
the MoA preset schema. It rejects a switch while the local endpoint reports an
active request.

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
bash -n deploy/flight-engineer-control deploy/install-host-control.sh
hermes plugins doctor . --ci
hermes plugins compat .
```

## License

MIT
