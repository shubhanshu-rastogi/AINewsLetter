import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, RunListItem, Sources, Workflows } from "../api";
import { RunBadge } from "../components/RunState";

export default function Dashboard() {
  const nav = useNavigate();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setRuns(await Workflows.list());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load runs");
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  async function trigger() {
    setStarting(true);
    setError(null);
    try {
      const res = await Workflows.start();
      nav(`/runs/${res.workflow_run_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start run");
      setStarting(false);
    }
  }

  async function seed() {
    setSeedMsg(null);
    try {
      const res = await Sources.seed();
      setSeedMsg(res.message);
    } catch (err) {
      setSeedMsg(err instanceof ApiError ? err.message : "Seeding failed");
    }
  }

  const active = runs.find((r) => r.run_state === "running" || r.run_state === "awaiting_review");
  const recent = runs.slice(0, 8);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Trigger and monitor newsletter generation runs.</p>
        </div>
        <button className="btn btn-primary" onClick={trigger} disabled={starting}>
          {starting ? <span className="spin" /> : "＋ Trigger new issue"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {active && (
        <div className="card" style={{ borderColor: "var(--accent-dim)" }}>
          <div className="row">
            <h2 style={{ margin: 0 }}>
              {active.title ?? `Issue #${active.issue_number ?? "?"}`}
            </h2>
            <RunBadge state={active.run_state} />
            <div className="spacer" />
            <button className="btn btn-sm" onClick={() => nav(`/runs/${active.workflow_run_id}`)}>
              Open live view →
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Recent runs</h2>
          <div className="spacer" />
          <button className="btn btn-ghost btn-sm" onClick={seed} title="Load the curated source list">
            Seed sources
          </button>
        </div>
        {seedMsg && <div className="notice" style={{ marginBottom: 12 }}>{seedMsg}</div>}
        {recent.length === 0 ? (
          <div className="empty">No runs yet. Trigger your first issue above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Issue</th>
                <th>Title</th>
                <th>State</th>
                <th>Newsletter</th>
                <th>Started</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.workflow_run_id}>
                  <td>#{r.issue_number ?? "—"}</td>
                  <td>{r.title ?? "—"}</td>
                  <td>
                    <RunBadge state={r.run_state} />
                  </td>
                  <td className="muted">{r.newsletter_status ?? "—"}</td>
                  <td className="faint">{fmt(r.started_at ?? r.created_at)}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => nav(`/runs/${r.workflow_run_id}`)}>
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
