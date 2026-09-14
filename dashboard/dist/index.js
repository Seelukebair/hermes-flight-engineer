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
  function safePromptText(value) { return value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, ""); }

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

  function EditableText(props) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(props.value || "");
    useEffect(function () { setDraft(props.value || ""); }, [props.value]);
    const clean = draft.trim();
    const valid = props.allowEmpty || Boolean(clean);
    function save() {
      if (!valid || draft === props.value) return;
      props.onSave(props.allowEmpty ? draft.trim() : clean);
      setEditing(false);
    }
    return h("div", { className: "flight-engineer-editable", onClick: props.stopPropagation ? function (event) { event.stopPropagation(); } : undefined },
      props.label ? h("span", { className: "flight-engineer-editable-label" }, props.label) : null,
      h("div", { className: "flight-engineer-editable-control" }, editing ? h(React.Fragment, null,
        h("input", { value: draft, maxLength: props.maxLength || 240, autoFocus: true, "aria-label": props.label || props.ariaLabel || "Editable value",
          onChange: function (event) { setDraft(event.target.value); },
          onKeyDown: function (event) { if (event.key === "Enter") save(); if (event.key === "Escape") { setDraft(props.value || ""); setEditing(false); } } }),
        h(Button, { size: "sm", disabled: props.busy || !valid || draft === props.value, onClick: save }, "Save"),
        h("button", { type: "button", className: "flight-engineer-editable-cancel", title: "Cancel edit", "aria-label": "Cancel edit",
          onClick: function () { setDraft(props.value || ""); setEditing(false); } }, "x")) : h(React.Fragment, null,
        h("span", { className: "flight-engineer-editable-value", title: props.value || "Not set" }, props.value || "Not set"),
        h("button", { type: "button", className: "flight-engineer-editable-open", title: "Edit " + (props.label || props.ariaLabel || "value"), "aria-label": "Edit " + (props.label || props.ariaLabel || "value"),
          onClick: function () { setEditing(true); } }, "\u270e"))));
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
    const [methodPickerOpen, setMethodPickerOpen] = useState(false);
    const [methodSearch, setMethodSearch] = useState("");
    const [methodFilter, setMethodFilter] = useState("all");
    useEffect(function () { setDraft(Object.assign({}, profile)); }, [profile]);
    function setValue(key, value) { setDraft(function (current) { return Object.assign({}, current, { [key]: value }); }); }
    const runtimeKeys = ["context_length", "parallel_slots", "gpu_layers", "kv_cache", "mmproj_offload", "batch_size", "ubatch_size", "image_min_tokens", "image_max_tokens"];
    const runtimeChanged = runtimeKeys.some(function (key) { return draft[key] !== profile[key]; });
    const assigned = ((props.jailbreaks || {}).assignments || {})[profile.id] || {};
    const selectedRecipes = Object.keys(assigned).map(function (kind) {
      return ((props.jailbreaks || {}).recipes || []).find(function (recipe) { return recipe.id === assigned[kind]; });
    }).filter(Boolean);
    const availableRecipes = ((props.jailbreaks || {}).recipes || []).filter(function (recipe) {
      const query = methodSearch.trim().toLowerCase();
      return recipe.enabled && assigned[recipe.type] !== recipe.id &&
        (methodFilter === "all" || recipe.type === methodFilter) &&
        (!query || (recipe.name + " " + (recipe.description || "")).toLowerCase().includes(query));
    });

    return h("details", { className: "flight-engineer-profile", "data-active": String(profile.active) },
      h("summary", null,
        h("div", { className: "flight-engineer-profile-identity" },
          h(EditableText, { value: profile.label, ariaLabel: "profile name", maxLength: 80, busy: props.busy, stopPropagation: true,
            onSave: function (value) { props.onSave(profile.id, { label: value }); } }),
          h("span", { className: "flight-engineer-primary-model" }, profile.model_file || "model unavailable")),
        h("div", { className: "flight-engineer-summary-actions" },
          profile.default ? h(Badge, null, "default") : null,
          profile.active ? h(Badge, null, "active") : null,
          h("span", { className: "flight-engineer-chevron", "aria-hidden": "true" }, "v"))),
      h("div", { className: "flight-engineer-profile-body" },
        h("div", { className: "flight-engineer-profile-meta" }, profile.description),
        locked ? h("div", { className: "flight-engineer-lock-note" }, "Validated runtime settings are locked. Duplicate this profile before tuning.") : null,
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
        h(SettingSection, { title: "Jailbreak methods" },
          h("div", { className: "flight-engineer-method-manager" },
            h("p", { className: "flight-engineer-helper" }, "Attach up to one saved entry of each type. Adding another entry of the same type replaces the current one."),
            h("div", { className: "flight-engineer-profile-methods" },
              selectedRecipes.map(function (recipe) {
                return h("div", { key: recipe.id, className: "flight-engineer-method-chip" },
                  h("span", null, recipe.name), h(TypeTag, { type: recipe.type }),
                  h("button", { type: "button", title: "Remove " + recipe.name, "aria-label": "Remove " + recipe.name, onClick: function () { props.onRemoveJailbreak(profile.id, recipe.type); } }, "x"));
              }),
              h("button", { type: "button", className: "flight-engineer-method-add", title: "Add a jailbreak method", "aria-label": "Add a jailbreak method", "aria-expanded": String(methodPickerOpen), onClick: function () { setMethodPickerOpen(!methodPickerOpen); } }, "+")),
            methodPickerOpen ? h("div", { className: "flight-engineer-method-selector" },
              h("div", { className: "flight-engineer-method-selector-tools" },
                h("input", { type: "search", value: methodSearch, placeholder: "Search saved methods", "aria-label": "Search saved jailbreak methods", onChange: function (event) { setMethodSearch(event.target.value); } }),
                h("div", { className: "flight-engineer-method-filters", role: "group", "aria-label": "Filter jailbreak methods by type" },
                  [["all", "All"], ["system_framing", "System"], ["thinking_prefill", "Thinking"], ["assistant_prefill", "Assistant"]].map(function (option) {
                    return h("button", { key: option[0], type: "button", "data-type": option[0], className: methodFilter === option[0] ? "is-active" : "", onClick: function () { setMethodFilter(option[0]); } }, option[1]);
                  }))),
              h("div", { className: "flight-engineer-method-results" }, availableRecipes.length ? availableRecipes.map(function (recipe) {
                return h("button", { key: recipe.id, type: "button", onClick: function () { props.onAssignJailbreak(profile.id, recipe.id); setMethodPickerOpen(false); setMethodSearch(""); } },
                  h("span", null, recipe.name), h(TypeTag, { type: recipe.type }));
              }) : h("span", { className: "flight-engineer-helper" }, "No matching saved methods. Create one in the library below."))) : null)),
        h("section", { className: "flight-engineer-profile-actions" },
          h("div", { className: "flight-engineer-profile-actions-heading" },
            h("strong", null, "Profile actions"),
            h("span", null, profile.active ? "This profile is currently loaded." : "Loading changes the local model backend.")),
          locked ? h("details", { className: "flight-engineer-clone" },
            h("summary", null, "Create editable tuning copy"),
            h("div", { className: "flight-engineer-clone-form" },
              h(Field, { label: "Copy name" }, h("input", { value: cloneLabel, "aria-label": "New tuning profile name", onChange: function (e) { setCloneLabel(e.target.value); } })),
              h(Field, { label: "Internal profile id" }, h("input", { value: cloneId, "aria-label": "New tuning profile id", onChange: function (e) { setCloneId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-")); } })),
              h(Button, { outlined: true, disabled: props.busy || !cloneLabel.trim() || !cloneId.trim(), onClick: function () { props.onClone(profile.id, cloneId, cloneLabel); } }, "Create copy"))) : null,
          h("div", { className: "flight-engineer-actions" },
          !locked ? h(Button, { outlined: true, disabled: props.busy || !runtimeChanged, onClick: function () {
            const runtime = {}; runtimeKeys.forEach(function (key) { if (draft[key] !== profile[key]) runtime[key] = draft[key]; });
            props.onSave(profile.id, { runtime: runtime });
          } }, "Save settings") : null,
          !profile.default ? h(Button, { outlined: true, disabled: props.busy, onClick: function () { props.onDefault(profile.id); } }, "Make default after reboot") : null,
          h(Button, { disabled: props.busy || !props.confirmed, onClick: function () { profile.active ? props.onApply(profile.id) : props.onSwitch(profile.id); } }, profile.active ? "Reload active profile" : "Load profile")))));
  }

  const injectionHelp = {
    system_framing: "Injects text into Hermes's system prompt before generation. This provides strong instruction-level steering, but it is more likely to conflict with Hermes policy or tool guidance.",
    thinking_prefill: "Starts a compatible model's private reasoning channel through the reasoning_content field. Think formats are not standardized; use this only with a profile validated for that runtime and chat template.",
    assistant_prefill: "Starts the visible assistant answer with your text and asks the model to continue it. This is the simplest refusal-steering method, but the opening may appear in the reply."
  };
  const injectionLabels = { system_framing: "System prompt injection", thinking_prefill: "Thinking prefill", assistant_prefill: "Assistant prefill" };

  function TypeTag(props) {
    return h("span", { className: "flight-engineer-type-tag", "data-type": props.type }, injectionLabels[props.type]);
  }

  function RecipeRow(props) {
    const recipe = props.recipe;
    const [draft, setDraft] = useState(Object.assign({}, recipe));
    const [secret, setSecret] = useState("");
    useEffect(function () { setDraft(Object.assign({}, recipe)); }, [recipe]);
    function setValue(key, value) { setDraft(function (current) { return Object.assign({}, current, { [key]: value }); }); }
    function save() {
      const pending = secret.trim() ? [{ technique: recipe.type, value: secret }] : [];
      props.onSave(recipe.id, { name: draft.name, description: draft.description, enabled: draft.enabled, profile_ids: draft.profile_ids || [] }, pending);
      setSecret("");
    }
    return h("details", { className: "flight-engineer-recipe" },
      h("summary", null,
        h("div", { className: "flight-engineer-recipe-title", title: "Internal id: " + recipe.id }, h("strong", null, recipe.name), h(TypeTag, { type: recipe.type })),
          h("div", { className: "flight-engineer-summary-actions" },
            h(Badge, null, recipe.enabled ? "enabled" : "disabled"),
          h(Badge, null, recipe.configured ? "configured" : "empty"),
          h("span", { className: "flight-engineer-chevron", "aria-hidden": "true" }, "v"))),
      h("div", { className: "flight-engineer-recipe-body" },
        h("div", { className: "flight-engineer-recipe-grid" },
          h(EditableText, { label: "Friendly name", value: recipe.name, maxLength: 80, busy: props.busy,
            onSave: function (value) { props.onSave(recipe.id, { name: value }, []); } }),
          h(EditableText, { label: "What this entry is for", value: recipe.description || "", maxLength: 240, allowEmpty: true, busy: props.busy,
            onSave: function (value) { props.onSave(recipe.id, { description: value }, []); } })),
        h("div", { className: "flight-engineer-compatibility" },
          h("strong", null, "Used by profiles"),
          h("span", { className: "flight-engineer-helper" }, (props.usedProfileIds || []).length ? "This entry is currently attached to these profiles." : "Not attached to a profile yet."),
          h("div", { className: "flight-engineer-profile-checks" }, props.profiles.filter(function (profile) { return (props.usedProfileIds || []).includes(profile.id); }).map(function (profile) {
            return h("span", { key: profile.id, title: profile.model_file || profile.id }, profile.label);
          }))),
        h("section", { className: "flight-engineer-injection-type" },
          h("textarea", { value: secret, rows: 4, maxLength: 16000,
            placeholder: recipe.configured ? "Protected value configured. Enter replacement text, or leave blank to keep it." : "Enter protected " + injectionLabels[recipe.type].toLowerCase() + " text",
            "aria-label": injectionLabels[recipe.type] + " protected text", onChange: function (e) { setSecret(safePromptText(e.target.value)); } }),
          recipe.configured ? h(Button, { outlined: true, disabled: props.busy, onClick: function () { props.onClear(recipe.id, recipe.type); } }, "Clear protected text") : null),
        h("div", { className: "flight-engineer-actions" },
          h("label", { className: "flight-engineer-toggle" }, h("input", { type: "checkbox", checked: Boolean(draft.enabled), onChange: function (e) { setValue("enabled", e.target.checked); } }), h("span", null, "Entry available")),
          h(Button, { outlined: true, disabled: props.busy, onClick: function () { props.onClone(recipe); } }, "Clone"),
          h(Button, { outlined: true, disabled: props.busy, onClick: function () { if (window.confirm("Delete this library entry and its protected text?")) props.onDelete(recipe.id); } }, "Delete"),
          h(Button, { disabled: props.busy, onClick: save }, "Save changes"))));
  }

  function JailbreakPanel(props) {
    const data = props.data || { enabled: false, assignments: {}, recipes: [] };
    const [newId, setNewId] = useState(""), [newName, setNewName] = useState("");
    const [newSecret, setNewSecret] = useState("");
    const [newType, setNewType] = useState("system_framing");
    const [visibleTypes, setVisibleTypes] = useState(function () {
      return Object.keys(injectionLabels).reduce(function (result, kind) { result[kind] = true; return result; }, {});
    });
    const visibleRecipes = data.recipes.filter(function (recipe) { return Boolean(visibleTypes[recipe.type]); });
    function toggleVisibleType(kind) {
      setVisibleTypes(function (current) { return Object.assign({}, current, { [kind]: !current[kind] }); });
    }
    function updateNewName(value) {
      setNewName(value);
      const base = value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48);
      const used = new Set(data.recipes.map(function (recipe) { return recipe.id; }));
      let candidate = base, suffix = 2;
      while (candidate && used.has(candidate)) candidate = base.slice(0, 58) + "-" + suffix++;
      setNewId(candidate);
    }
    const header = h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" },
        h("div", null, h(CardTitle, null, "Jailbreak methods"), h("div", { className: "flight-engineer-stat-label" }, "Filter the saved library by method type; protected text is write-only")),
        h("label", { className: "flight-engineer-toggle" }, h("input", { type: "checkbox", checked: Boolean(data.enabled), disabled: props.busy,
          onChange: function (e) { props.onConfigure({ enabled: e.target.checked }); } }), h("span", null, data.enabled ? "Methods active" : "All methods off"))));
    const content = h(CardContent, null,
        h("div", { className: "flight-engineer-warning" }, "Prompt injection can reduce refusals, but it can also weaken tool discipline or response quality. Attach saved entries from inside each model profile."),
        h("div", { className: "flight-engineer-type-tabs", role: "group", "aria-label": "Filter saved jailbreak methods by type" }, Object.keys(injectionLabels).map(function (kind) {
          const count = data.recipes.filter(function (recipe) { return recipe.type === kind; }).length;
          const enabled = Boolean(visibleTypes[kind]);
          return h("button", { key: kind, type: "button", "data-type": kind, "aria-pressed": String(enabled), className: enabled ? "is-active" : "", onClick: function () { toggleVisibleType(kind); } },
            h("strong", null, injectionLabels[kind]), h("span", null, count + " saved"));
        })),
        h("details", { className: "flight-engineer-create" }, h("summary", null, "Create library entry"),
          h("div", { className: "flight-engineer-create-row" },
            h("label", null, h("span", null, "Friendly name"), h("input", { value: newName, placeholder: "Friendly name", maxLength: 80, onChange: function (e) { updateNewName(e.target.value); } })),
            h("label", null, h("span", null, "Method type"), h("select", { value: newType, onChange: function (e) { setNewType(e.target.value); } }, Object.keys(injectionLabels).map(function (kind) {
              return h("option", { key: kind, value: kind }, injectionLabels[kind]);
            })))),
          h("p", { className: "flight-engineer-type-help" }, injectionHelp[newType]),
          h("div", { className: "flight-engineer-create-text" },
            h("label", null, "Protected " + injectionLabels[newType].toLowerCase() + " text"),
            h("p", { className: "flight-engineer-helper" }, "This value is write-only after saving. Quotes, braces, Unicode, and multiple lines are safe; unsupported control characters are rejected."),
            h("textarea", { value: newSecret, rows: 6, maxLength: 16000, placeholder: "Enter the actual injection text", onChange: function (e) { setNewSecret(safePromptText(e.target.value)); } })),
          h("div", { className: "flight-engineer-create-actions" },
            h(Button, { outlined: true, disabled: props.busy || !newId || !newName || !newSecret.trim(), onClick: function () { props.onCreate(newId, newName, newType, newSecret); setVisibleTypes(function (current) { return Object.assign({}, current, { [newType]: true }); }); setNewId(""); setNewName(""); setNewSecret(""); } }, "Save to library"))),
        h("details", { className: "flight-engineer-library", open: visibleRecipes.length > 0 },
          h("summary", null, "Saved library entries (" + visibleRecipes.length + " of " + data.recipes.length + ")"),
          h("div", { className: "flight-engineer-recipes" }, visibleRecipes.length ? visibleRecipes.map(function (recipe) {
            const usedProfileIds = props.profiles.filter(function (profile) { return Object.values(data.assignments[profile.id] || {}).includes(recipe.id); }).map(function (profile) { return profile.id; });
            return h(RecipeRow, { key: recipe.id, recipe: recipe, profiles: props.profiles, usedProfileIds: usedProfileIds, busy: props.busy, onSave: props.onSave, onClear: props.onClear, onDelete: props.onDelete, onClone: props.onClone });
          }) : h("p", { className: "flight-engineer-helper" }, data.recipes.length ? "No saved entries match the enabled method filters." : "No saved entries yet. Create one here, then attach it with the + button inside a model profile."))));
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
    function configureJailbreaks(patch) { return mutate(async function () {
      setJailbreaks(await request("/jailbreaks", { method: "PATCH", body: JSON.stringify(patch) }));
    }, "Jailbreak configuration saved."); }
    function createJailbreak(id, name, recipeType, value) { return mutate(function () { return request("/jailbreaks", { method: "POST", body: JSON.stringify({ recipe_id: id, name: name, recipe_type: recipeType, value: value }) }); }, "Jailbreak entry and protected text saved."); }
    function saveJailbreak(id, patch, secrets) { return mutate(async function () {
      await request("/jailbreaks/" + encodeURIComponent(id), { method: "PATCH", body: JSON.stringify(patch) });
      for (const secret of secrets) await request("/jailbreaks/" + encodeURIComponent(id) + "/secrets/" + secret.technique, { method: "PUT", body: JSON.stringify({ value: secret.value }) });
    }, "Recipe saved; protected editors were cleared."); }
    function clearJailbreakSecret(id, technique) { return mutate(function () { return request("/jailbreaks/" + encodeURIComponent(id) + "/secrets/" + technique, { method: "PUT", body: JSON.stringify({ value: "" }) }); }, "Protected text removed."); }
    function deleteJailbreak(id) { return mutate(function () { return request("/jailbreaks/" + encodeURIComponent(id), { method: "DELETE" }); }, "Recipe and protected text removed."); }
    function assignJailbreak(profileId, recipeId) { return configureJailbreaks({ profile_id: profileId, recipe_id: recipeId }); }
    function removeJailbreak(profileId, technique) { return configureJailbreaks({ profile_id: profileId, recipe_id: null, technique: technique }); }
    function cloneJailbreak(recipe) {
      const name = window.prompt("Name for the cloned entry", recipe.name + " copy");
      if (!name) return;
      const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 52) || "recipe-copy";
      const target = base + "-" + Date.now().toString(36).slice(-5);
      return mutate(function () { return request("/jailbreaks/clone", { method: "POST", body: JSON.stringify({ source_id: recipe.id, target_id: target, name: name }) }); }, "Entry cloned with its protected text.");
    }
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
        h(CardContent, null, error ? h("p", { className: "flight-engineer-error" }, error) : null, notice ? h("p", { className: "flight-engineer-notice" }, notice) : null, h("div", { className: "flight-engineer-profiles" }, profiles.map(function (profile) { return h(ProfileRow, { key: profile.id, profile: profile, jailbreaks: jailbreaks, busy: busy, confirmed: confirmed, onSave: saveProfile, onClone: cloneProfile, onApply: applyProfile, onSwitch: switchProfile, onDefault: setDefaultProfile, onAssignJailbreak: assignJailbreak, onRemoveJailbreak: removeJailbreak }); })))),
      h(JailbreakPanel, { data: jailbreaks, profiles: profiles, busy: busy, onConfigure: configureJailbreaks, onCreate: createJailbreak, onSave: saveJailbreak, onClear: clearJailbreakSecret, onDelete: deleteJailbreak, onClone: cloneJailbreak }));
  }
  window.__HERMES_PLUGINS__.register("flight-engineer", FlightEngineerPage);
})();
