---
name: flight-engineer
description: Inspect and switch validated local inference backend profiles while preserving Hermes native model and Mixture of Agents behavior.
---

# Flight Engineer

Hermes is the orchestrator. Flight Engineer manages tested configurations for
the supporting local inference backend. It does not replace Hermes model
selection, fallbacks, delegation, or Mixture of Agents.

This plugin skill is exposed to Hermes as
`flight-engineer:flight-engineer`. Use that qualified name for explicit skill
loading; normal profile-intent turns also receive the plugin's bounded context
hook.

Use the `flight_engineer` tool to inspect status and available profiles. The
stable Hermes provider/model pair remains
`gemma4-thinker-local/gemma4-thinker`, including when native MoA uses it as a
reference or aggregator. A profile switch changes the validated backend behind
that alias; profiles are not simultaneously loaded models.

Before a switch or rollback:

1. Call `status` and `list`.
2. Explain which profile will be loaded, its production/tuning status, and that
   active local inference will be interrupted during loading and acceptance.
3. Proceed only when the user's request explicitly authorizes that profile
   change. Set `confirm_interrupt` to true only then.
4. Report the returned active profile and service state. Never claim success
   from intent alone.

Never invent a profile id, expose arbitrary runtime arguments, use a force
option, edit Hermes configuration directly, or switch profiles during an
active MoA request. Treat `tuning` and `experimental` profiles as evaluations,
not accepted production defaults. Use Hermes's native Models/MoA settings to
choose where the stable local route participates.

`use` loads a profile immediately and interrupts local inference. `set_default`
selects the next boot profile together with its linked native Hermes MoA preset.
The running profile and active MoA mode stay as they are. Call `set_default`
when the user asks to make a profile the default, then report the returned
active profile, boot profile, and linked preset when available.

## Jailbreak Recipes

Flight Engineer can assign reusable prompt-injection recipes to compatible
local model profiles. Recipe names, descriptions, compatibility, assignments,
and configured/not-configured flags are visible. The actual system framing,
thinking prefill, and assistant prefill text is protected and write-only: never
claim to read, repeat, summarize, or reveal it.

Use `list_jailbreaks` before changing recipe state. Each named entry belongs to
exactly one injection type. `assign_jailbreak` maps an existing compatible
entry to one profile; provide the technique when clearing one type.
`set_jailbreak_enabled` is the global switch. Change either only when the user
explicitly requests it. A recipe assignment does not switch model profiles.

Injection types are intentionally distinct:

- System prompt injection appends instructions to the system message. It is strong but
  may conflict with Hermes tool and safety guidance.
- Thinking prefill starts a compatible model's private reasoning channel. It
  steers approach but is not intended as visible answer text.
- Assistant prefill starts the visible answer and asks the model to continue.
  Its opening may be returned to the user.

Injection runs only on the initial user request, never on a tool-result
continuation. Unknown or merely similar models never inherit a recipe
automatically. Prompt injection can lower refusal behavior, tool discipline,
or response quality; do not describe it as guaranteed.
