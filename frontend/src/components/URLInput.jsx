import { useState, useRef } from 'react';
import { analyzeURL } from '../api';
import { connectAnalyze } from '../ws';
import AnalysisProgress from './AnalysisProgress';

export default function URLInput({ onAnalyzed }) {
  const [url, setUrl] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [createMarket, setCreateMarket] = useState(false);
  const [progress, setProgress] = useState(null); // { step, progress, message }
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const progressRef = useRef(null);

  const reset = () => {
    setAnalyzing(false);
    setProgress(null);
  };

  const fallbackREST = async (targetUrl) => {
    setProgress({ step: 'analyzing', progress: 0.5, message: 'Falling back to REST...' });
    try {
      const result = await analyzeURL(targetUrl);
      setUrl('');
      setProgress({ step: 'done', progress: 1, message: 'Done!' });
      onAnalyzed?.(result);
      setTimeout(reset, 1500);
    } catch (err) {
      setError(err.message);
      setTimeout(reset, 3000);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed || analyzing) return;

    setAnalyzing(true);
    setError(null);
    setProgress({ step: 'fetching', progress: 0, message: 'Connecting...' });

    progressRef.current = 'fetching';

    const handle = connectAnalyze(trimmed, createMarket, {
      onProgress(data) {
        progressRef.current = data.step;
        setProgress(data);
      },
      onDone(result) {
        setUrl('');
        setProgress({ step: 'done', progress: 1, message: 'Done!' });
        onAnalyzed?.(result);
        setTimeout(reset, 1500);
      },
      onError(msg) {
        // If WebSocket fails before any real progress, fallback to REST
        if (!progressRef.current || progressRef.current === 'fetching') {
          fallbackREST(trimmed);
        } else {
          setError(msg);
          setTimeout(reset, 3000);
        }
      },
    });

    wsRef.current = handle;
  };

  const handleCancel = () => {
    wsRef.current?.close();
    reset();
    setError(null);
  };

  return (
    <div className="url-input-wrapper">
      <form className="url-input" onSubmit={handleSubmit}>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste article URL to analyze..."
          disabled={analyzing}
        />
        <label className="market-toggle" title="Auto-create Truth Market for verifiable claims">
          <input
            type="checkbox"
            checked={createMarket}
            onChange={(e) => setCreateMarket(e.target.checked)}
            disabled={analyzing}
          />
          <span>Market</span>
        </label>
        {analyzing ? (
          <button type="button" onClick={handleCancel} className="cancel-btn">
            Cancel
          </button>
        ) : (
          <button type="submit" disabled={!url.trim()}>
            Analyze
          </button>
        )}
      </form>

      {analyzing && (
        <AnalysisProgress
          step={progress?.step}
          progress={progress?.progress}
          message={progress?.message}
          error={error}
        />
      )}

      {!analyzing && error && <span className="url-input-error">{error}</span>}
    </div>
  );
}
