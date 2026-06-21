import { useEffect, useMemo, useState } from "react";
import { ApiError, ConfigField, ConfigPayload, Settings } from "../api";

export default function SettingsPage() {
  const [payload, setPayload] = useState<ConfigPayload | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const p = await Settings.get();
      setPayload(p);
      const init: Record<string, unknown> = {};
      for (const f of p.fields) init[f.key] = f.type === "secret" ? "" : p.values[f.key];
      setForm(init);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load settings");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const groups = useMemo(() => {
    const g: Record<string, ConfigField[]> = {};
    for (const f of payload?.fields ?? []) (g[f.group] ??= []).push(f);
    return g;
  }, [payload]);

  function set(key: string, value: unknown) {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(null);
  }

  async function save() {
    if (!payload) return;
    setSaving(true);
    setError(null);
    setSaved(null);
    const updates: Record<string, unknown> = {};
    for (const f of payload.fields) {
      if (f.type === "secret") {
        if (form[f.key] !== "" && form[f.key] != null) updates[f.key] = form[f.key];
      } else if (form[f.key] !== payload.values[f.key]) {
        updates[f.key] = form[f.key];
      }
    }
    if (Object.keys(updates).length === 0) {
      setSaved("No changes to save.");
      setSaving(false);
      return;
    }
    try {
      const res = await Settings.update(updates);
      setPayload(res);
      const init: Record<string, unknown> = {};
      for (const f of res.fields) init[f.key] = f.type === "secret" ? "" : res.values[f.key];
      setForm(init);
      setSaved(`Saved ${res.changed.length} setting(s).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!payload) {
    return (
      <div className="empty">
        {error ? <div className="error-banner">{error}</div> : <span className="spin" />}
      </div>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>API keys, models, and feature flags. Secrets are encrypted at rest.</p>
        </div>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? <span className="spin" /> : "Save changes"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {saved && <div className="notice" style={{ marginBottom: 16 }}>{saved}</div>}

      <div className="notice" style={{ marginBottom: 16 }}>
        Tip: features stay in safe offline mode until you turn on the matching toggle and provide its key.
      </div>

      {Object.entries(groups).map(([group, fields]) => (
        <div className="card" key={group}>
          <h2>{group}</h2>
          <div className="grid grid-2">
            {fields.map((f) => (
              <Field
                key={f.key}
                field={f}
                value={form[f.key]}
                secretSet={payload.secret_set[f.key]}
                onChange={(v) => set(f.key, v)}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function Field({
  field,
  value,
  secretSet,
  onChange,
}: {
  field: ConfigField;
  value: unknown;
  secretSet?: boolean;
  onChange: (v: unknown) => void;
}) {
  if (field.type === "bool") {
    return (
      <div className="field">
        <label className="toggle">
          <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          {field.label}
        </label>
        {field.help && <div className="help">{field.help}</div>}
      </div>
    );
  }

  return (
    <div className="field">
      <label>
        {field.label}
        {field.type === "secret" && secretSet && (
          <span className="badge badge-completed" style={{ marginLeft: 8 }}>
            set
          </span>
        )}
      </label>
      {field.type === "select" ? (
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          {field.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : field.type === "number" ? (
        <input type="number" value={Number(value ?? 0)} onChange={(e) => onChange(Number(e.target.value))} />
      ) : field.type === "secret" ? (
        <input
          type="password"
          value={String(value ?? "")}
          placeholder={secretSet ? "•••••••• (leave blank to keep)" : "Not set"}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input type="text" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
      )}
      {field.help && <div className="help">{field.help}</div>}
    </div>
  );
}
