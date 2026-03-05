const BASE = '/api';

export async function fetchGraph(topic) {
  const params = topic ? `?topic=${encodeURIComponent(topic)}` : '';
  const res = await fetch(`${BASE}/graph${params}`);
  if (!res.ok) throw new Error(`fetchGraph failed: ${res.status}`);
  return res.json(); // { nodes, edges }
}

export async function analyzeURL(url) {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `analyzeURL failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchEntities(tier) {
  const params = tier ? `?tier=${encodeURIComponent(tier)}` : '';
  const res = await fetch(`${BASE}/entities${params}`);
  if (!res.ok) throw new Error(`fetchEntities failed: ${res.status}`);
  return res.json(); // { entities, total }
}

export async function fetchEntity(canonicalId) {
  const res = await fetch(`${BASE}/entities/${encodeURIComponent(canonicalId)}`);
  if (!res.ok) throw new Error(`fetchEntity failed: ${res.status}`);
  return res.json();
}

export async function search(query) {
  const res = await fetch(`${BASE}/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json(); // { query, entities, claims }
}

export async function fetchArticles() {
  const res = await fetch(`${BASE}/articles`);
  if (!res.ok) throw new Error(`fetchArticles failed: ${res.status}`);
  return res.json(); // { articles, total }
}

export async function fetchMarkets() {
  const res = await fetch(`${BASE}/markets`);
  if (!res.ok) throw new Error(`fetchMarkets failed: ${res.status}`);
  return res.json(); // { markets, total }
}

export async function fetchMarketDetail(marketId) {
  const res = await fetch(`${BASE}/markets/${encodeURIComponent(marketId)}`);
  if (!res.ok) throw new Error(`fetchMarketDetail failed: ${res.status}`);
  return res.json();
}

export async function triggerCREVerify(marketId) {
  const res = await fetch(`${BASE}/markets/${encodeURIComponent(marketId)}/cre-verify`, {
    method: 'POST',
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `triggerCREVerify failed: ${res.status}`);
  }
  return res.json();
}
