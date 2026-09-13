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

Active and default are distinct. `use` loads a profile immediately and is
interrupting. `set_default` changes only the profile selected on the next host
boot and does not interrupt current inference. Call `set_default` only when the
user explicitly asks to make a profile the default, then report both returned
active and default profile ids. Never imply that changing the default also
loaded the profile.
