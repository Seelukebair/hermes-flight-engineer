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

## Install

```bash
hermes plugins install Seelukebair/hermes-flight-engineer --no-enable
sudo FLIGHT_ENGINEER_OPERATOR="$USER" bash ~/.hermes/plugins/flight-engineer/deploy/install-host-control.sh
hermes plugins enable flight-engineer
```

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

