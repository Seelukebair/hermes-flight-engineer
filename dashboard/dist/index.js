(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const { useCallback, useEffect, useState } = SDK.hooks;
  const { Badge, Button, Card, CardContent, CardHeader, CardTitle } = SDK.components;
  const h = React.createElement;
  const API = "/api/plugins/flight-engineer";

  async function request(path, options) {
    const response = await fetch(API + path, Object.assign({
      headers: { "Content-Type": "application/json" }
    }, options || {}));
    const body = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(body.detail || "Flight Engineer request failed");
    return body;
  }

  function Stat(props) {
    return h("div", { className: "flight-engineer-stat" },
      h("div", { className: "flight-engineer-stat-label" }, props.label),
      h("div", { className: "flight-engineer-stat-value" }, props.value || "unknown")
    );
  }

  function FlightEngineerPage() {
    const [status, setStatus] = useState(null);
    const [profiles, setProfiles] = useState([]);
    const [confirmed, setConfirmed] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    const refresh = useCallback(async function () {
      setError("");
      try {
        const values = await Promise.all([request("/status"), request("/profiles")]);
        setStatus(values[0]);
        setProfiles(values[1].profiles || []);
      } catch (err) {
        setError(String(err.message || err));
      }
    }, []);

    useEffect(function () { refresh(); }, [refresh]);

    async function switchProfile(profileId) {
      setBusy(true);
      setError("");
      try {
        await request("/switch", {
          method: "POST",
          body: JSON.stringify({ profile_id: profileId, confirm_interrupt: confirmed })
        });
        setConfirmed(false);
        await refresh();
      } catch (err) {
        setError(String(err.message || err));
      } finally {
        setBusy(false);
      }
    }

    async function rollbackProfile() {
      setBusy(true);
      setError("");
      try {
        await request("/rollback", {
          method: "POST",
          body: JSON.stringify({ confirm_interrupt: confirmed })
        });
        setConfirmed(false);
        await refresh();
      } catch (err) {
        setError(String(err.message || err));
      } finally {
        setBusy(false);
      }
    }

    const services = status && status.services ? status.services : {};
    const healthy = Object.keys(services).length > 0 && Object.values(services).every(function (v) { return v === "active"; });
    const route = status && status.stable_route ? status.stable_route.provider + "/" + status.stable_route.model : "unknown";

    return h("div", { className: "flight-engineer-page" },
      h(Card, null,
        h(CardHeader, null,
          h("div", { className: "flight-engineer-profile-head" },
            h("div", null,
              h(CardTitle, null, "Flight Engineer"),
              h("div", { className: "flight-engineer-stat-label" }, "Tested inference configurations behind one Hermes-native route")
            ),
            h("div", { className: "flight-engineer-actions" },
              h(Button, {
                outlined: true,
                onClick: rollbackProfile,
                disabled: busy || !confirmed
              }, "Rollback"),
              h(Button, { outlined: true, onClick: refresh, disabled: busy }, "Refresh")
            )
          )
        ),
        h(CardContent, null,
          h("div", { className: "flight-engineer-summary" },
            h(Stat, { label: "Active profile", value: status && status.active_profile }),
            h(Stat, { label: "Profile state", value: status && status.profile_status }),
            h(Stat, { label: "Context", value: status && Number(status.context_length).toLocaleString() }),
            h(Stat, { label: "Backend health", value: healthy ? "all services active" : "attention required" })
          )
        )
      ),
      h(Card, null,
        h(CardHeader, null,
          h("div", { className: "flight-engineer-profile-head" },
            h("div", null,
              h(CardTitle, null, "Hermes route"),
              h("div", { className: "flight-engineer-profile-meta" }, route)
            ),
            h(Button, { outlined: true, onClick: function () { window.location.href = "/models"; } }, "Open MoA settings")
          )
        )
      ),
      h(Card, null,
        h(CardHeader, null,
          h("div", { className: "flight-engineer-profile-head" },
            h(CardTitle, null, "Validated profiles"),
            h("label", { className: "flight-engineer-confirm" },
              h("input", {
                type: "checkbox",
                checked: confirmed,
                onChange: function (event) { setConfirmed(event.target.checked); }
              }),
              "Allow an interrupting profile change"
            )
          )
        ),
        h(CardContent, null,
          error ? h("p", { className: "flight-engineer-error" }, error) : null,
          h("div", { className: "flight-engineer-profiles" }, profiles.map(function (profile) {
            const kv = profile.kv_cache ? String(profile.kv_cache).toUpperCase() + " KV" : "KV unknown";
            const meta = "ctx " + Number(profile.context_length || 0).toLocaleString() +
              " | " + profile.parallel_slots + " slots | " + kv + " | " + profile.gpu_layers + " GPU layers";
            return h("div", { className: "flight-engineer-profile", "data-active": String(profile.active), key: profile.id },
              h("div", { className: "flight-engineer-profile-head" },
                h("strong", null, profile.label),
                h(Badge, null, profile.active ? "active" : profile.status)
              ),
              h("div", { className: "flight-engineer-profile-meta" }, meta),
              h("div", { className: "flight-engineer-actions" },
                h("span", { className: "flight-engineer-stat-label" }, profile.description),
                h(Button, {
                  size: "sm",
                  disabled: busy || profile.active || !confirmed,
                  onClick: function () { switchProfile(profile.id); }
                }, profile.active ? "Loaded" : "Load")
              )
            );
          }))
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("flight-engineer", FlightEngineerPage);
})();
