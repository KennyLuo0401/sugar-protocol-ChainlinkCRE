const STEPS = [
  { key: 'fetching', label: 'Fetching' },
  { key: 'classifying', label: 'Classifying' },
  { key: 'analyzing', label: 'Analyzing' },
  { key: 'resolving', label: 'Resolving' },
  { key: 'saving', label: 'Saving' },
  { key: 'done', label: 'Done' },
];

export default function AnalysisProgress({ step, progress, message, error }) {
  const currentIdx = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="analysis-progress">
      <div className="progress-steps">
        {STEPS.map((s, i) => {
          let status = 'pending';
          if (error) {
            status = i <= currentIdx ? 'error' : 'pending';
          } else if (i < currentIdx) {
            status = 'done';
          } else if (i === currentIdx) {
            status = step === 'done' ? 'done' : 'active';
          }

          return (
            <div key={s.key} className={`progress-step ${status}`}>
              <div className="step-dot" />
              <span className="step-label">{s.label}</span>
            </div>
          );
        })}
      </div>

      <div className="progress-bar-track">
        <div
          className={`progress-bar-fill${error ? ' error' : ''}`}
          style={{ width: `${(progress ?? 0) * 100}%` }}
        />
      </div>

      {message && <div className="progress-message">{message}</div>}
      {error && <div className="progress-error">{error}</div>}
    </div>
  );
}
