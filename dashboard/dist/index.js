(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const { useCallback, useEffect, useState } = SDK.hooks;
  const { Badge, Button, Card, CardContent, CardHeader, CardTitle } = SDK.components;
  const h = React.createElement;
  const API = "/api/plugins/flight-engineer";

  async function request(path, options) {
    const response = await fetch(API + path, Object.assign({ headers: { "Content-Type": "application/json" } }, options || {}));
    const body = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(body.detail || "Flight Engineer request failed");
    return body;
  }

  function number(value) { return Number(value || 0).toLocaleString(); }

  function Stat(props) {
    return h("div", { className: "flight-engineer-stat" },
      h("div", { className: "flight-engineer-stat-label" }, props.label),
      h("div", { className: "flight-engineer-stat-value" }, props.value || "unknown"));
  }

  function LevelMeter(props) {
    const percent = Math.max(0, Math.min(100, Number(props.percent || 0)));
    const active = Math.ceil(percent / 100 * 16);
    const zone = percent >= 90 ? "danger" : percent >= 70 ? "warning" : "normal";
    return h("div", { className: "flight-engineer-meter", "data-zone": zone },
      h("span", { className: "flight-engineer-meter-label" }, props.label),
      h("div", { className: "flight-engineer-meter-track" },
        h("span", { "aria-hidden": "true" }, props.minLabel),
        h("div", { className: "flight-engineer-meter-bars", "aria-label": props.label + " " + props.value },
          Array.from({ length: 16 }, function (_, index) {
            return h("i", { key: index, className: index < active ? "is-lit" : "" });
          })),
        h("span", { "aria-hidden": "true" }, props.maxLabel)),
      h("strong", { className: "flight-engineer-meter-value" }, props.value));
  }

  function Field(props) {
    return h("label", { className: "flight-engineer-field" }, h("span", null, props.label), props.children);
  }

  function Stepper(props) {
    const value = Number(props.value || 0);
    const step = props.step || 1;
    const percent = Math.max(0, Math.min(100, (value - props.min) / (props.max - props.min) * 100));
    const active = Math.round(percent / 100 * 14);
    function adjust(delta) { props.onChange(Math.max(props.min, Math.min(props.max, value + delta))); }
    return h("div", { className: "flight-engineer-stepper", "data-disabled": String(props.disabled) },
      h("span", { className: "flight-engineer-stepper-label" }, props.label),
      h("div", { className: "flight-engineer-setting-track", "aria-hidden": "true" },
        h("span", null, number(props.min)),
        h("div", { className: "flight-engineer-setting-leds" },
          Array.from({ length: 14 }, function (_, index) { return h("i", { key: index, className: index < active ? "is-lit" : "" }); })),
        h("span", null, number(props.max))),
      h("div", { className: "flight-engineer-stepper-controls" },
        h("button", { type: "button", title: "Decrease " + props.label, "aria-label": "Decrease " + props.label, disabled: props.disabled || value <= props.min, onClick: function () { adjust(-step); } }, "-"),
        h("input", { type: "number", min: props.min, max: props.max, step: step, value: value, disabled: props.disabled,
          "aria-label": props.label, onChange: function (event) { props.onChange(Number(event.target.value)); } }),
        h("button", { type: "button", title: "Increase " + props.label, "aria-label": "Increase " + props.label, disabled: props.disabled || value >= props.max, onClick: function () { adjust(step); } }, "+")));
  }

  function SettingSection(props) {
    return h("section", { className: "flight-engineer-setting-section" },
      h("h4", null, props.title), h("div", { className: "flight-engineer-fields" }, props.children));
  }

  function ProfileRow(props) {
    const profile = props.profile;
    const locked = profile.status === "production";
    const [draft, setDraft] = useState(Object.assign({}, profile));
    const [cloneId, setCloneId] = useState(profile.id + "-tuning");
    const [cloneLabel, setCloneLabel] = useState(profile.label + " (tuning)");
    useEffect(function () { setDraft(Object.assign({}, profile)); }, [profile]);
    function setValue(key, value) { setDraft(function (current) { return Object.assign({}, current, { [key]: value }); }); }
    const runtimeKeys = ["context_length", "parallel_slots", "gpu_layers", "kv_cache", "mmproj_offload", "batch_size", "ubatch_size", "image_min_tokens", "image_max_tokens"];
    const runtimeChanged = runtimeKeys.some(function (key) { return draft[key] !== profile[key]; });
    const labelChanged = draft.label !== profile.label;

    return h("details", { className: "flight-engineer-profile", "data-active": String(profile.active) },
      h("summary", null,
        h("div", { className: "flight-engineer-profile-identity" },
          h("input", { className: "flight-engineer-profile-name", value: draft.label, "aria-label": "Profile name",
            onClick: function (event) { event.stopPropagation(); }, onChange: function (event) { setValue("label", event.target.value); } }),
          h("span", { className: "flight-engineer-primary-model" }, profile.model_file || "model unavailable")),
        h("div", { className: "flight-engineer-summary-actions" },
          labelChanged ? h(Button, { size: "sm", outlined: true, disabled: props.busy,
            onClick: function (event) { event.preventDefault(); event.stopPropagation(); props.onSave(profile.id, { label: draft.label }); } }, "Save name") : null,
          profile.default ? h(Badge, null, "default") : null,
          h(Badge, null, profile.active ? "active" : profile.status), h("span", { className: "flight-engineer-chevron", "aria-hidden": "true" }, "v"))),
      h("div", { className: "flight-engineer-profile-body" },
        h("div", { className: "flight-engineer-profile-meta" }, profile.description),
        locked ? h("div", { className: "flight-engineer-lock-note" }, "Accepted production runtime is locked. Duplicate it before tuning.") : null,
        h(SettingSection, { title: "Runtime capacity" },
          h(Stepper, { label: "Max concurrent inference", value: draft.parallel_slots, min: 1, max: 8, disabled: locked, onChange: function (v) { setValue("parallel_slots", v); } }),
          h(Stepper, { label: "Context size", value: draft.context_length, min: 8192, max: 1048576, step: 8192, disabled: locked, onChange: function (v) { setValue("context_length", v); } }),
          h(Stepper, { label: "GPU layers", value: draft.gpu_layers, min: 1, max: 999, disabled: locked, onChange: function (v) { setValue("gpu_layers", v); } })),
        h(SettingSection, { title: "Memory and placement" },
          h(Field, { label: "KV cache precision" }, h("select", { value: draft.kv_cache, disabled: locked, onChange: function (e) { setValue("kv_cache", e.target.value); } },
            h("option", { value: "q8_0" }, "Q8_0"), h("option", { value: "f16" }, "F16"), h("option", { value: "fp8" }, "FP8"))),
          h("label", { className: "flight-engineer-toggle" }, h("input", { type: "checkbox", checked: Boolean(draft.mmproj_offload), disabled: locked, onChange: function (e) { setValue("mmproj_offload", e.target.checked); } }), h("span", null, "Vision projector on GPU"))),
        h(SettingSection, { title: "Request processing" },
          h(Stepper, { label: "Batch size", value: draft.batch_size, min: 32, max: 2048, step: 32, disabled: locked, onChange: function (v) { setValue("batch_size", v); } }),
          h(Stepper, { label: "Micro-batch size", value: draft.ubatch_size, min: 32, max: 2048, step: 32, disabled: locked, onChange: function (v) { setValue("ubatch_size", v); } })),
        h(SettingSection, { title: "Vision token budget" },
          h(Stepper, { label: "Minimum image tokens", value: draft.image_min_tokens, min: 64, max: 4096, step: 64, disabled: locked, onChange: function (v) { setValue("image_min_tokens", v); } }),
          h(Stepper, { label: "Maximum image tokens", value: draft.image_max_tokens, min: 64, max: 4096, step: 64, disabled: locked, onChange: function (v) { setValue("image_max_tokens", v); } })),
        locked ? h("div", { className: "flight-engineer-clone" },
          h("input", { value: cloneLabel, "aria-label": "New tuning profile name", onChange: function (e) { setCloneLabel(e.target.value); } }),
          h("input", { value: cloneId, "aria-label": "New tuning profile id", onChange: function (e) { setCloneId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-")); } }),
          h(Button, { outlined: true, disabled: props.busy, onClick: function () { props.onClone(profile.id, cloneId, cloneLabel); } }, "Duplicate for tuning")) : null,
        h("div", { className: "flight-engineer-actions" },
          !locked ? h(Button, { outlined: true, disabled: props.busy || (!runtimeChanged && !labelChanged), onClick: function () {
            const runtime = {}; runtimeKeys.forEach(function (key) { if (draft[key] !== profile[key]) runtime[key] = draft[key]; });
            props.onSave(profile.id, { label: draft.label, runtime: runtimeChanged ? runtime : undefined });
          } }, "Save settings") : null,
          h(Button, { outlined: true, disabled: props.busy || profile.default, onClick: function () { props.onDefault(profile.id); } }, profile.default ? "Default" : "Make default"),
          h(Button, { disabled: props.busy || !props.confirmed, onClick: function () { profile.active ? props.onApply(profile.id) : props.onSwitch(profile.id); } }, profile.active ? "Apply & reload" : "Load profile"))));
  }

  const injectionHelp = {
    system_framing: "Adds instructions to Hermes's system message before generation. Strong and persistent for the request, but more likely to conflict with Hermes policy or tool guidance.",
    thinking_prefill: "Starts the model's private reasoning channel with your text. Useful for steering how a compatible reasoning model approaches the request; it is not spoken or shown as the answer.",
    assistant_prefill: "Starts the visible assistant answer with your text and asks the model to continue it. This is the simplest refusal-steering method, but the opening may appear in the reply."
  };
  const injectionLabels = { system_framing: "System framing", thinking_prefill: "Thinking prefill", assistant_prefill: "Assistant prefill" };

  function RecipeRow(props) {
    const recipe = props.recipe;
    const [draft, setDraft] = useState(Object.assign({}, recipe));
    const [secrets, setSecrets] = useState({ system_framing: "", thinking_prefill: "", assistant_prefill: "" });
    useEffect(function () { setDraft(Object.assign({}, recipe)); }, [recipe]);
    function setValue(key, value) { setDraft(function (current) { return Object.assign({}, current, { [key]: value }); }); }
    function toggleProfile(id) {
      const ids = new Set(draft.profile_ids || []);
      if (ids.has(id)) ids.delete(id); else ids.add(id);
      setValue("profile_ids", Array.from(ids));
    }
    function save() {
      const pending = Object.keys(secrets).filter(function (kind) { return secrets[kind].trim(); });
      props.onSave(recipe.id, { name: draft.name, description: draft.description, enabled: draft.enabled, profile_ids: draft.profile_ids || [] }, pending.map(function (kind) { return { technique: kind, value: secrets[kind] }; }));
      setSecrets({ system_framing: "", thinking_prefill: "", assistant_prefill: "" });
    }
    return h("details", { className: "flight-engineer-recipe" },
      h("summary", null,
        h("div", { className: "flight-engineer-recipe-title" }, h("strong", null, recipe.name), h("span", null, recipe.id)),
        h("div", { className: "flight-engineer-summary-actions" },
          h(Badge, null, recipe.enabled ? "enabled" : "disabled"),
          h(Badge, null, Object.values(recipe.techniques || {}).filter(Boolean).length + "/3 configured"),
          h("span", { className: "flight-engineer-chevron", "aria-hidden": "true" }, "v"))),
      h("div", { className: "flight-engineer-recipe-body" },
        h("div", { className: "flight-engineer-recipe-grid" },
          h(Field, { label: "Friendly recipe name" }, h("input", { value: draft.name, maxLength: 80, onChange: function (e) { setValue("name", e.target.value); } })),
          h(Field, { label: "What this recipe is for" }, h("input", { value: draft.description || "", maxLength: 240, placeholder: "Short compatibility or behavior note", onChange: function (e) { setValue("description", e.target.value); } }))),
        h("div", { className: "flight-engineer-compatibility" },
          h("strong", null, "Compatible model profiles"),
          h("span", { className: "flight-engineer-helper" }, "A recipe can be reused, but it runs only on explicitly checked profiles."),
          h("div", { className: "flight-engineer-profile-checks" }, props.profiles.map(function (profile) {
            return h("label", { key: profile.id, title: profile.model_file || profile.id },
              h("input", { type: "checkbox", checked: (draft.profile_ids || []).includes(profile.id), onChange: function () { toggleProfile(profile.id); } }),
              h("span", null, profile.label));
          }))),
        Object.keys(injectionLabels).map(function (kind) {
          const configured = Boolean((recipe.techniques || {})[kind]);
          return h("section", { key: kind, className: "flight-engineer-injection-type" },
            h("div", { className: "flight-engineer-injection-heading" }, h("strong", null, injectionLabels[kind]), h(Badge, null, configured ? "configured" : "empty")),
            h("p", { className: "flight-engineer-helper" }, injectionHelp[kind]),
            h("textarea", { value: secrets[kind], rows: 3, maxLength: 16000,
              placeholder: configured ? "Protected value configured. Enter replacement text, or leave blank to keep it." : "Enter protected injection text",
              "aria-label": injectionLabels[kind] + " protected text",
              onChange: function (e) { setSecrets(Object.assign({}, secrets, { [kind]: e.target.value })); } }),
            configured ? h(Button, { outlined: true, disabled: props.busy, onClick: function () { props.onClear(recipe.id, kind); } }, "Clear protected text") : null);
        }),
        h("div", { className: "flight-engineer-actions" },
          h("label", { className: "flight-engineer-toggle" }, h("input", { type: "checkbox", checked: Boolean(draft.enabled), onChange: function (e) { setValue("enabled", e.target.checked); } }), h("span", null, "Recipe enabled")),
          h(Button, { disabled: props.busy, onClick: save }, "Save recipe"))));
  }

  function JailbreakPanel(props) {
    const data = props.data || { enabled: false, assignments: {}, recipes: [] };
    const [newId, setNewId] = useState(""), [newName, setNewName] = useState("");
    const header = h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" },
        h("div", null, h(CardTitle, null, "Jailbreak library"), h("div", { className: "flight-engineer-stat-label" }, "Reusable, model-labeled injection recipes; protected text is write-only")),
        h("label", { className: "flight-engineer-toggle" }, h("input", { type: "checkbox", checked: Boolean(data.enabled), disabled: props.busy,
          onChange: function (e) { props.onConfigure({ enabled: e.target.checked }); } }), h("span", null, data.enabled ? "Injection active" : "Injection off"))));
    const content = h(CardContent, null,
        h("div", { className: "flight-engineer-warning" }, "Prompt injection can reduce refusals, but it can also weaken tool discipline or response quality. Recipes apply only to explicitly compatible and assigned local profiles."),
        h("section", { className: "flight-engineer-assignments" }, h("h4", null, "Profile assignments"),
          h("div", { className: "flight-engineer-assignment-grid" }, props.profiles.map(function (profile) {
            const compatible = data.recipes.filter(function (recipe) { return recipe.enabled && (recipe.profile_ids || []).includes(profile.id); });
            return h(Field, { key: profile.id, label: profile.label }, h("select", { value: data.assignments[profile.id] || "", title: profile.model_file || profile.id,
              onChange: function (e) { props.onConfigure({ profile_id: profile.id, recipe_id: e.target.value || null }); } },
              h("option", { value: "" }, "No recipe"), compatible.map(function (recipe) { return h("option", { key: recipe.id, value: recipe.id }, recipe.name); })));
          }))),
        h("details", { className: "flight-engineer-create" }, h("summary", null, "Create recipe"),
          h("div", { className: "flight-engineer-create-row" },
            h("input", { value: newName, placeholder: "Friendly name", maxLength: 80, onChange: function (e) { setNewName(e.target.value); } }),
            h("input", { value: newId, placeholder: "short-recipe-id", maxLength: 64, onChange: function (e) { setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-")); } }),
            h(Button, { outlined: true, disabled: props.busy || !newId || !newName, onClick: function () { props.onCreate(newId, newName); setNewId(""); setNewName(""); } }, "Create"))),
        h("div", { className: "flight-engineer-recipes" }, data.recipes.length ? data.recipes.map(function (recipe) {
          return h(RecipeRow, { key: recipe.id, recipe: recipe, profiles: props.profiles, busy: props.busy, onSave: props.onSave, onClear: props.onClear });
        }) : h("p", { className: "flight-engineer-helper" }, "No recipes yet. Create one, mark compatible profiles, then assign it above.")));
    return h(Card, null, header, content);
  }

  function FlightEngineerPage() {
    const [status, setStatus] = useState(null), [profiles, setProfiles] = useState([]), [telemetry, setTelemetry] = useState(null);
    const [jailbreaks, setJailbreaks] = useState({ enabled: false, assignments: {}, recipes: [] });
    const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
    const refresh = useCallback(async function () { try { const values = await Promise.all([request("/status"), request("/profiles"), request("/jailbreaks")]); setStatus(values[0]); setProfiles(values[1].profiles || []); setJailbreaks(values[2]); setError(""); } catch (err) { setError(String(err.message || err)); } }, []);
    const refreshTelemetry = useCallback(async function () { try { setTelemetry(await request("/telemetry")); } catch (_) { setTelemetry(null); } }, []);
    useEffect(function () { refresh(); refreshTelemetry(); }, [refresh, refreshTelemetry]);
    useEffect(function () { const timer = window.setInterval(function () { if (!document.hidden) refreshTelemetry(); }, 2000); return function () { window.clearInterval(timer); }; }, [refreshTelemetry]);
    async function mutate(work, message) { setBusy(true); setError(""); setNotice(""); try { await work(); setNotice(message); await refresh(); await refreshTelemetry(); } catch (err) { setError(String(err.message || err)); } finally { setBusy(false); } }
    function switchProfile(id) { return mutate(function () { return request("/switch", { method: "POST", body: JSON.stringify({ profile_id: id, confirm_interrupt: confirmed }) }); }, "Profile loaded."); }
    function applyProfile(id) { return mutate(function () { return request("/profiles/" + encodeURIComponent(id) + "/apply", { method: "POST", body: JSON.stringify({ profile_id: id, confirm_interrupt: confirmed }) }); }, "Saved profile reloaded."); }
    function saveProfile(id, patch) { return mutate(function () { return request("/profiles/" + encodeURIComponent(id), { method: "PATCH", body: JSON.stringify(patch) }); }, "Profile saved. Reload the active profile to apply runtime changes."); }
    function cloneProfile(source, target, label) { return mutate(function () { return request("/profiles/clone", { method: "POST", body: JSON.stringify({ source_id: source, target_id: target, label: label }) }); }, "Tuning profile created."); }
    function setDefaultProfile(id) { return mutate(function () { return request("/profiles/" + encodeURIComponent(id) + "/default", { method: "POST" }); }, "Default profile changed for the next host boot."); }
    function rollbackProfile() { return mutate(function () { return request("/rollback", { method: "POST", body: JSON.stringify({ confirm_interrupt: confirmed }) }); }, "Previous profile restored."); }
    function configureJailbreaks(patch) { return mutate(function () { return request("/jailbreaks", { method: "PATCH", body: JSON.stringify(patch) }); }, "Jailbreak configuration saved."); }
    function createJailbreak(id, name) { return mutate(function () { return request("/jailbreaks", { method: "POST", body: JSON.stringify({ recipe_id: id, name: name }) }); }, "Jailbreak recipe created."); }
    function saveJailbreak(id, patch, secrets) { return mutate(async function () {
      await request("/jailbreaks/" + encodeURIComponent(id), { method: "PATCH", body: JSON.stringify(patch) });
      for (const secret of secrets) await request("/jailbreaks/" + encodeURIComponent(id) + "/secrets/" + secret.technique, { method: "PUT", body: JSON.stringify({ value: secret.value }) });
    }, "Recipe saved; protected editors were cleared."); }
    function clearJailbreakSecret(id, technique) { return mutate(function () { return request("/jailbreaks/" + encodeURIComponent(id) + "/secrets/" + technique, { method: "PUT", body: JSON.stringify({ value: "" }) }); }, "Protected text removed."); }
    const services = status && status.services ? status.services : {};
    const healthy = Object.keys(services).length > 0 && Object.values(services).every(function (v) { return v === "active"; });
    const route = status && status.stable_route ? status.stable_route.provider + "/" + status.stable_route.model : "unknown";
    const inf = telemetry ? telemetry.inference : {}, sys = telemetry ? telemetry.system : {};
    const slotPercent = inf.slots ? inf.active / inf.slots * 100 : 0, vramPercent = sys.vram_total_mb ? sys.vram_used_mb / sys.vram_total_mb * 100 : 0;
    const ramPercent = sys.ram_total_mb ? sys.ram_used_mb / sys.ram_total_mb * 100 : 0, powerPercent = sys.gpu_power_limit_w ? sys.gpu_power_w / sys.gpu_power_limit_w * 100 : 0;
    const contextPercent = inf.context_per_slot ? inf.context_tokens_used / inf.context_per_slot * 100 : 0;
    return h("div", { className: "flight-engineer-page" },
      h(Card, null, h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" }, h("div", null, h(CardTitle, null, "Flight Engineer"), h("div", { className: "flight-engineer-stat-label" }, "Validated local inference configurations")), h("div", { className: "flight-engineer-actions" }, h(Button, { outlined: true, onClick: rollbackProfile, disabled: busy || !confirmed }, "Rollback"), h(Button, { outlined: true, onClick: refresh, disabled: busy }, "Refresh")))),
        h(CardContent, null, h("div", { className: "flight-engineer-summary" }, h(Stat, { label: "Active profile", value: status && status.active_profile }), h(Stat, { label: "Default after reboot", value: status && status.default_profile }), h(Stat, { label: "Hermes route", value: route }), h(Stat, { label: "Context", value: status && number(status.context_length) }), h(Stat, { label: "Backend health", value: healthy ? "all services active" : "attention required" })))),
      h(Card, null, h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" }, h("div", null, h(CardTitle, null, "Live inference"), h("div", { className: "flight-engineer-stat-label" }, telemetry ? "Updates every 2 seconds" : "Telemetry unavailable")), h("div", { className: "flight-engineer-live-copy" }, number(inf.current_tokens_per_second) + " tok/s now | " + number(inf.queued) + " queued"))),
        h(CardContent, null, h("div", { className: "flight-engineer-meter-layout" },
          h(LevelMeter, { label: "Active slots", percent: slotPercent, value: number(inf.active) + " / " + number(inf.slots), minLabel: "0", maxLabel: number(inf.slots) }),
          h(LevelMeter, { label: "Context high-water", percent: contextPercent, value: number(inf.context_tokens_used) + " / " + number(inf.context_per_slot), minLabel: "0", maxLabel: number(inf.context_per_slot) }),
          h(LevelMeter, { label: "GPU load", percent: sys.gpu_percent, value: number(sys.gpu_percent) + "% | " + number(sys.gpu_temperature_c) + " C", minLabel: "0%", maxLabel: "100%" }),
          h(LevelMeter, { label: "VRAM", percent: vramPercent, value: number(sys.vram_used_mb) + " / " + number(sys.vram_total_mb) + " MB", minLabel: "0", maxLabel: number(sys.vram_total_mb) + " MB" }),
          h(LevelMeter, { label: "GPU power", percent: powerPercent, value: number(sys.gpu_power_w) + " W", minLabel: "0 W", maxLabel: number(sys.gpu_power_limit_w) + " W" }),
          h(LevelMeter, { label: "CPU load", percent: sys.cpu_load_percent, value: number(sys.cpu_load_percent) + "%", minLabel: "0%", maxLabel: "100%" }),
          h(LevelMeter, { label: "System memory", percent: ramPercent, value: number(sys.ram_used_mb) + " / " + number(sys.ram_total_mb) + " MB", minLabel: "0", maxLabel: number(sys.ram_total_mb) + " MB" })))),
      h(Card, null, h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" }, h("div", null, h(CardTitle, null, "Model profiles"), h("div", { className: "flight-engineer-stat-label" }, "Profile name and primary model stay visible; expand to tune runtime settings")), h("div", { className: "flight-engineer-actions" }, h("label", { className: "flight-engineer-confirm" }, h("input", { type: "checkbox", checked: confirmed, onChange: function (e) { setConfirmed(e.target.checked); } }), "Allow interrupting reloads"), h(Button, { outlined: true, onClick: function () { window.location.href = "/models"; } }, "Open MoA settings")))),
        h(CardContent, null, error ? h("p", { className: "flight-engineer-error" }, error) : null, notice ? h("p", { className: "flight-engineer-notice" }, notice) : null, h("div", { className: "flight-engineer-profiles" }, profiles.map(function (profile) { return h(ProfileRow, { key: profile.id, profile: profile, busy: busy, confirmed: confirmed, onSave: saveProfile, onClone: cloneProfile, onApply: applyProfile, onSwitch: switchProfile, onDefault: setDefaultProfile }); })))),
      h(JailbreakPanel, { data: jailbreaks, profiles: profiles, busy: busy, onConfigure: configureJailbreaks, onCreate: createJailbreak, onSave: saveJailbreak, onClear: clearJailbreakSecret }));
  }
  window.__HERMES_PLUGINS__.register("flight-engineer", FlightEngineerPage);
})();
