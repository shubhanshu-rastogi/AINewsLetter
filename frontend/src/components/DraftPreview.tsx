// Renders the newsletter draft content dict. Falls back to pretty JSON for
// anything it doesn't have a dedicated renderer for.

type Content = Record<string, unknown>;

function asArray(v: unknown): Content[] {
  return Array.isArray(v) ? (v as Content[]) : [];
}
function str(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : JSON.stringify(v);
}

export default function DraftPreview({ content }: { content: Content }) {
  const cover = content.cover as Content | undefined;
  const topStories = asArray(content.top_stories);
  const tools = asArray(content.tools);
  const trends = asArray(content.trends);
  const takeaways = Array.isArray(content.final_takeaways)
    ? (content.final_takeaways as unknown[]).map(str)
    : [];

  return (
    <div>
      {cover && (
        <div className="draft-section">
          <h2 style={{ marginBottom: 2 }}>{str(cover.title) || "Newsletter"}</h2>
          {cover.issue_number != null && <div className="faint">Issue #{str(cover.issue_number)}</div>}
        </div>
      )}

      {content.executive_summary != null && (
        <div className="draft-section">
          <h3>Executive summary</h3>
          <p>{str(content.executive_summary)}</p>
        </div>
      )}

      {topStories.length > 0 && (
        <div className="draft-section">
          <h3>Top stories</h3>
          {topStories.map((s, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <strong>{str(s.headline) || `Story ${i + 1}`}</strong>
              {s.what_happened != null && <p className="muted" style={{ margin: "4px 0" }}>{str(s.what_happened)}</p>}
              {s.why_it_matters != null && (
                <p className="faint" style={{ margin: "4px 0" }}>Why it matters: {str(s.why_it_matters)}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {tools.length > 0 && (
        <div className="draft-section">
          <h3>Tools worth watching</h3>
          <ul>
            {tools.map((t, i) => (
              <li key={i}>{str(t.name) || str(t.headline) || JSON.stringify(t)}</li>
            ))}
          </ul>
        </div>
      )}

      {trends.length > 0 && (
        <div className="draft-section">
          <h3>Trend signals</h3>
          <ul>
            {trends.map((t, i) => (
              <li key={i}>{str(t.title) || str(t)}</li>
            ))}
          </ul>
        </div>
      )}

      {takeaways.length > 0 && (
        <div className="draft-section">
          <h3>Final takeaways</h3>
          <ul>
            {takeaways.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="draft-section">
        <summary className="faint" style={{ cursor: "pointer" }}>
          Raw content (JSON)
        </summary>
        <pre style={{ overflow: "auto", fontSize: 12 }}>
          <code>{JSON.stringify(content, null, 2)}</code>
        </pre>
      </details>
    </div>
  );
}
