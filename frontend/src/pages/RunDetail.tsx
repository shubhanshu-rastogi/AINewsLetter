import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ApiError, Newsletters, WorkflowStatus, Workflows } from "../api";
// Newsletters.htmlUrl provides the shareable web-page link.
import { ProgressBar, RunBadge, Stepper } from "../components/RunState";
import DraftPreview from "../components/DraftPreview";

const POLL_MS = 1500;
const LIVE_STATES = new Set(["running", "awaiting_review"]);

export default function RunDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const timer = useRef<number | null>(null);

  const poll = useCallback(async () => {
    try {
      const s = await Workflows.status(id);
      setStatus(s);
      if (s.newsletter_id && (s.run_state === "awaiting_review" || s.run_state === "completed")) {
        try {
          const nl = await Newsletters.get(s.newsletter_id);
          setDraft(nl.content);
        } catch {
          /* draft may not be ready yet */
        }
      }
      return s;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load run");
      return null;
    }
  }, [id]);

  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      const s = await poll();
      if (!mounted) return;
      if (s && LIVE_STATES.has(s.run_state)) {
        timer.current = window.setTimeout(tick, POLL_MS);
      }
    };
    tick();
    return () => {
      mounted = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [poll]);

  async function review(decision: string) {
    setSubmitting(true);
    setError(null);
    try {
      await Workflows.review(id, decision, decision === "feedback_required" ? feedback : undefined);
      setShowFeedback(false);
      setFeedback("");
      // Resume polling for the post-review progress.
      const s = await poll();
      if (s && LIVE_STATES.has(s.run_state)) {
        timer.current = window.setTimeout(async function tick() {
          const n = await poll();
          if (n && LIVE_STATES.has(n.run_state)) timer.current = window.setTimeout(tick, POLL_MS);
        }, POLL_MS);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Review failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!status) {
    return (
      <div className="empty">
        {error ? <div className="error-banner">{error}</div> : <span className="spin" />}
      </div>
    );
  }

  const awaiting = status.run_state === "awaiting_review";
  const terminal = ["completed", "rejected", "failed"].includes(status.run_state);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="row">
            <h1 style={{ margin: 0 }}>Issue run</h1>
            <RunBadge state={status.run_state} />
          </div>
          <p>
            <code>{id}</code>
          </p>
        </div>
        <button className="btn btn-ghost" onClick={() => nav("/history")}>
          ← All runs
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <div className="progress-meta">
          <span>{status.current_stage ?? "Starting"}</span>
          <span>{status.progress_percent}%</span>
        </div>
        <ProgressBar percent={status.progress_percent} state={status.run_state} />
        <Stepper stages={status.stages} />
      </div>

      {status.errors.length > 0 && (
        <div className="card">
          <h3>Errors</h3>
          {status.errors.map((e, i) => (
            <div key={i} className="error-banner" style={{ marginBottom: 8 }}>
              {e}
            </div>
          ))}
        </div>
      )}

      {awaiting && (
        <div className="card">
          <h2>Review &amp; decide</h2>
          <p className="muted">The workflow is paused awaiting your decision.</p>
          {showFeedback ? (
            <div className="field">
              <label>What should change?</label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g. Tighten the intro and add a stronger QA angle to the lead story."
                autoFocus
              />
              <div className="row" style={{ marginTop: 10 }}>
                <button
                  className="btn btn-amber"
                  disabled={submitting || !feedback.trim()}
                  onClick={() => review("feedback_required")}
                >
                  {submitting ? <span className="spin" /> : "Submit feedback & regenerate"}
                </button>
                <button className="btn btn-ghost" onClick={() => setShowFeedback(false)} disabled={submitting}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="row">
              <button className="btn btn-green" disabled={submitting} onClick={() => review("approved")}>
                ✓ Approve &amp; publish
              </button>
              <button className="btn btn-amber" disabled={submitting} onClick={() => setShowFeedback(true)}>
                ✎ Request changes
              </button>
              <button className="btn btn-red" disabled={submitting} onClick={() => review("rejected")}>
                ✕ Reject
              </button>
            </div>
          )}
        </div>
      )}

      {terminal && (
        <div className="card">
          <h3>Outcome</h3>
          <dl className="kv">
            <dt>Run state</dt>
            <dd>
              <RunBadge state={status.run_state} />
            </dd>
            <dt>Approval</dt>
            <dd className="muted">{status.approval_status ?? "—"}</dd>
            <dt>Publish status</dt>
            <dd className="muted">{status.publish_status ?? "—"}</dd>
          </dl>
        </div>
      )}

      {draft && (
        <div className="card">
          <div className="row" style={{ marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Draft preview</h2>
            <div className="spacer" />
            {status.newsletter_id && (
              <a
                className="btn btn-sm"
                href={Newsletters.htmlUrl(status.newsletter_id)}
                target="_blank"
                rel="noopener noreferrer"
              >
                View web page ↗
              </a>
            )}
          </div>
          <DraftPreview content={draft} />
        </div>
      )}
    </>
  );
}
