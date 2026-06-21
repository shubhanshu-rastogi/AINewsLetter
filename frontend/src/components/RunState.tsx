import { RunState, Stage } from "../api";

const LABELS: Record<string, string> = {
  running: "Running",
  awaiting_review: "Awaiting review",
  completed: "Completed",
  rejected: "Rejected",
  failed: "Failed",
  pending: "Pending",
};

export function RunBadge({ state }: { state: RunState | null | undefined }) {
  const s = state ?? "pending";
  return <span className={`badge dot badge-${s}`}>{LABELS[s] ?? s}</span>;
}

export function ProgressBar({ percent, state }: { percent: number; state: RunState | null | undefined }) {
  const cls = state === "completed" ? "done" : state === "failed" ? "failed" : "";
  return (
    <div className="progress">
      <div className={`progress-fill ${cls}`} style={{ width: `${Math.max(2, percent)}%` }} />
    </div>
  );
}

export function Stepper({ stages }: { stages: Stage[] }) {
  return (
    <div className="stepper">
      {stages.map((s, i) => (
        <div key={s.key} className={`step ${s.state}`}>
          <span className="step-icon">
            {s.state === "done" ? "✓" : s.state === "failed" ? "!" : i + 1}
          </span>
          <span className="step-label">{s.label}</span>
        </div>
      ))}
    </div>
  );
}
