import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, RunListItem, Workflows } from "../api";
import { RunBadge } from "../components/RunState";

export default function History() {
  const nav = useNavigate();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setRuns(await Workflows.list());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load history");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>History</h1>
          <p>Every newsletter run and its outcome.</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        {loading ? (
          <div className="empty">
            <span className="spin" />
          </div>
        ) : runs.length === 0 ? (
          <div className="empty">No runs recorded yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Issue</th>
                <th>Title</th>
                <th>State</th>
                <th>Newsletter</th>
                <th>Created</th>
                <th>Finished</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.workflow_run_id}>
                  <td>#{r.issue_number ?? "—"}</td>
                  <td>{r.title ?? "—"}</td>
                  <td>
                    <RunBadge state={r.run_state} />
                  </td>
                  <td className="muted">{r.newsletter_status ?? "—"}</td>
                  <td className="faint">{fmt(r.created_at)}</td>
                  <td className="faint">{fmt(r.finished_at)}</td>
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
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
