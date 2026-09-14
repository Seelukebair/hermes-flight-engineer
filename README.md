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

- `flight_engineer` agent tool: status, list, guarded use, default selection,
  and rollback.
- `hermes flight-engineer`: the same operations for operators.
- `flight-engineer:flight-engineer` plugin skill: teaches Hermes the safety and
  native MoA boundary. Plugin skills are namespaced in current Hermes; the bare
  name is not valid for `--skills` preloading.
- Dashboard tab: live inference/system meters, collapsed profile rows, bounded
  tuning controls, active/default selection, profile-attached jailbreak
methods, a compact reusable library, and a link to native MoA settings.
  Existing text fields use a reusable pencil, text box, Save, and Cancel
  interaction; runtime settings retain their separate save action.
  Locked-profile duplication is collapsed behind `Create editable tuning copy`
  with labeled name/id fields; profile actions use compact, normal typography.
- Root-owned control wrapper: permits named profile operations and bounded JSON
  edits on stdin; no arbitrary shell, paths, images, force switch, or services.

## Current Driver Contract

Version 0.2 targets the JSON status and profile-manifest contract provided by
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
only enumerated operations, validates every profile id, and cannot forward
force flags or arbitrary arguments. Runtime edits are parsed and validated by
the root-owned manager from an 8 KiB JSON request on stdin. Every edit is backed
up; accepted production runtime settings must first be duplicated to a tuning
profile. Profile manifests and the manager remain root-owned.

`Load profile` activates a profile now. `Make default` selects what loads once
at the next host boot; normal service reloads preserve the current selection.
Saving an active tuning profile does not silently restart inference. Use the
separate confirmed `Apply & reload` action.

## Jailbreak Method Library

Version 0.4 keeps three explicit method types: system prompt injection, thinking
prefill, and assistant prefill. The library's three colored buttons are
independent view filters and start enabled; turning one off hides that method
type without changing entries or profile assignments. New entries choose their
method type inside the create form. Attach methods from the expanded model profile
with its `+` picker. The bounded selector searches by name/description and can
filter all, system, thinking, or assistant entries without expanding for a large
library. Selected methods appear by friendly name and a color-coded
type tag. A profile can use one entry of each type; choosing another entry of the
same type replaces that type without disturbing the others.

The compact library creates, edits, clones, disables, and deletes reusable
entries. Profile attachment automatically records explicit compatibility. No
fuzzy model matching is used for prompt injection.

Generated internal ids are env-safe and receive `-2`, `-3`, and later suffixes
when a friendly-name slug already exists. Prompt bodies may contain normal JSON,
quotes, braces, Unicode, and line breaks; malformed Unicode and unsafe control
characters are rejected before storage.

System prompt injection and assistant prefill use standard chat-message fields.
Thinking prefill currently uses `reasoning_content`, whose interpretation is
runtime and chat-template specific. Treat it as profile-compatible only after
validation; model-specific think-token adapters are intentionally not guessed.

Prompt bodies are stored through Hermes's profile-scoped `.env` writer. They
are write-only in the dashboard and agent tool: APIs expose only recipe
metadata and configured flags. The optional loopback adapter forwards to the
unchanged llama.cpp service and injects only when the last request message is a
user message, so tool-result continuations are not modified. Global injection
is off until explicitly enabled.

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
