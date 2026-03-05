/**
 * WebSocket client for real-time analysis progress.
 *
 * Usage:
 *   connectAnalyze(articleUrl, { onProgress, onDone, onError })
 *   → returns a close() function to abort early
 */

function getWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/analyze`;
}

/**
 * Open a WebSocket to /ws/analyze, send the URL, and stream progress events.
 *
 * @param {string} articleUrl - The article URL to analyze
 * @param {object} callbacks
 * @param {(data: {step:string, progress:number, message:string}) => void} callbacks.onProgress
 * @param {(result: object) => void} callbacks.onDone
 * @param {(error: string) => void} callbacks.onError
 * @returns {{ close: () => void }} - Call close() to abort
 */
export function connectAnalyze(articleUrl, createMarket, { onProgress, onDone, onError }) {
  let ws;
  let closed = false;

  try {
    ws = new WebSocket(getWsUrl());
  } catch {
    onError?.('WebSocket connection failed');
    return { close() {} };
  }

  ws.onopen = () => {
    if (closed) return;
    ws.send(JSON.stringify({ url: articleUrl, create_market: !!createMarket }));
  };

  ws.onmessage = (event) => {
    if (closed) return;
    try {
      const data = JSON.parse(event.data);

      if (data.step === 'done') {
        onDone?.(data.result);
        ws.close();
      } else if (data.step === 'error') {
        onError?.(data.message || 'Analysis failed');
        ws.close();
      } else {
        onProgress?.(data);
      }
    } catch {
      onError?.('Invalid server message');
      ws.close();
    }
  };

  ws.onerror = () => {
    if (closed) return;
    onError?.('WebSocket connection error');
  };

  ws.onclose = () => {
    // No action needed — onDone or onError already fired
  };

  return {
    close() {
      closed = true;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
  };
}
