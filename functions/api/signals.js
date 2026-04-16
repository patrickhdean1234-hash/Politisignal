/**
 * Cloudflare Pages Function — Political Signals API
 * Serves signals.json with optional filtering
 *
 * GET /api/signals
 *   ?limit=50          max results (default 50, max 100)
 *   ?severity=critical filter by severity (critical|high|medium|low)
 *   ?ticker=NVDA       filter to signals mentioning this ticker
 *   ?politician=Warren filter by politician name (partial match)
 *   ?source=bluesky    filter by source platform
 *
 * No API key required for basic access.
 * Elite subscribers get the full unfiltered feed without rate limits.
 */

export async function onRequestGet(context) {
  const url = new URL(context.request.url);

  // Fetch signals.json from the same Pages deployment
  let signals = [];
  try {
    const base = new URL(context.request.url);
    base.pathname = '/data/signals.json';
    const r = await fetch(base.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });
    if (r.ok) signals = await r.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Failed to load signals', detail: String(e) }), {
      status: 502,
      headers: corsHeaders(),
    });
  }

  // ── Filters ──
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10), 100);
  const severity = url.searchParams.get('severity');
  const ticker   = url.searchParams.get('ticker')?.toUpperCase();
  const politician = url.searchParams.get('politician')?.toLowerCase();
  const source   = url.searchParams.get('source')?.toLowerCase();
  const since    = url.searchParams.get('since'); // ISO timestamp

  let result = signals;

  if (severity) result = result.filter(s => s.severity === severity);
  if (ticker)   result = result.filter(s => s.tickers?.includes(ticker));
  if (politician) result = result.filter(s => s.politician?.toLowerCase().includes(politician));
  if (source)   result = result.filter(s => (s.source || s.platform)?.toLowerCase().includes(source));
  if (since) {
    const sinceTs = new Date(since).getTime();
    if (!isNaN(sinceTs)) result = result.filter(s => {
      const pub = new Date(s.published_iso).getTime();
      return pub > sinceTs;
    });
  }

  result = result.slice(0, limit);

  const body = JSON.stringify({
    ok: true,
    count: result.length,
    total: signals.length,
    updated: signals[0]?.published_iso || null,
    signals: result,
  }, null, 2);

  return new Response(body, {
    headers: {
      ...corsHeaders(),
      'Cache-Control': 'public, max-age=60, s-maxage=60',
    },
  });
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders() });
}

function corsHeaders() {
  return {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
  };
}
