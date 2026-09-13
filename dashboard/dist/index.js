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

  function MeterSection(props) {
    return h("section", { className: "flight-engineer-meter-section" },
      h("h4", null, props.title), h("div", { className: "flight-engineer-meters" }, props.children));
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

  function FlightEngineerPage() {
    const [status, setStatus] = useState(null), [profiles, setProfiles] = useState([]), [telemetry, setTelemetry] = useState(null);
    const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
    const refresh = useCallback(async function () { try { const values = await Promise.all([request("/status"), request("/profiles")]); setStatus(values[0]); setProfiles(values[1].profiles || []); setError(""); } catch (err) { setError(String(err.message || err)); } }, []);
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
          h(MeterSection, { title: "Inference" },
            h(LevelMeter, { label: "Active slots", percent: slotPercent, value: number(inf.active) + " / " + number(inf.slots), minLabel: "0", maxLabel: number(inf.slots) }),
            h(LevelMeter, { label: "Context high-water", percent: contextPercent, value: number(inf.context_tokens_used) + " / " + number(inf.context_per_slot), minLabel: "0", maxLabel: number(inf.context_per_slot) })),
          h(MeterSection, { title: "Accelerator" },
            h(LevelMeter, { label: "GPU load", percent: sys.gpu_percent, value: number(sys.gpu_percent) + "% | " + number(sys.gpu_temperature_c) + " C", minLabel: "0%", maxLabel: "100%" }),
            h(LevelMeter, { label: "VRAM", percent: vramPercent, value: number(sys.vram_used_mb) + " / " + number(sys.vram_total_mb) + " MB", minLabel: "0", maxLabel: number(sys.vram_total_mb) + " MB" }),
            h(LevelMeter, { label: "GPU power", percent: powerPercent, value: number(sys.gpu_power_w) + " W", minLabel: "0 W", maxLabel: number(sys.gpu_power_limit_w) + " W" })),
          h(MeterSection, { title: "Host" },
            h(LevelMeter, { label: "CPU load", percent: sys.cpu_load_percent, value: number(sys.cpu_load_percent) + "%", minLabel: "0%", maxLabel: "100%" }),
            h(LevelMeter, { label: "System memory", percent: ramPercent, value: number(sys.ram_used_mb) + " / " + number(sys.ram_total_mb) + " MB", minLabel: "0", maxLabel: number(sys.ram_total_mb) + " MB" }))))),
      h(Card, null, h(CardHeader, null, h("div", { className: "flight-engineer-profile-head" }, h("div", null, h(CardTitle, null, "Model profiles"), h("div", { className: "flight-engineer-stat-label" }, "Profile name and primary model stay visible; expand to tune runtime settings")), h("div", { className: "flight-engineer-actions" }, h("label", { className: "flight-engineer-confirm" }, h("input", { type: "checkbox", checked: confirmed, onChange: function (e) { setConfirmed(e.target.checked); } }), "Allow interrupting reloads"), h(Button, { outlined: true, onClick: function () { window.location.href = "/models"; } }, "Open MoA settings")))),
        h(CardContent, null, error ? h("p", { className: "flight-engineer-error" }, error) : null, notice ? h("p", { className: "flight-engineer-notice" }, notice) : null, h("div", { className: "flight-engineer-profiles" }, profiles.map(function (profile) { return h(ProfileRow, { key: profile.id, profile: profile, busy: busy, confirmed: confirmed, onSave: saveProfile, onClone: cloneProfile, onApply: applyProfile, onSwitch: switchProfile, onDefault: setDefaultProfile }); })))));
  }
  window.__HERMES_PLUGINS__.register("flight-engineer", FlightEngineerPage);
})();
