/**
 * Cloudflare Pages Function — Real-time stock prices
 * Proxies Yahoo Finance with 60-second edge caching
 * GET /api/prices?tickers=AAPL,MSFT,NVDA or /api/prices (returns all defaults)
 */

const DEFAULT_TICKERS = [
  'SPY','QQQ','DIA','IWM',
  'AAPL','MSFT','GOOGL','AMZN','META','NVDA','TSLA','PLTR',
  'JPM','BAC','GS',
  'XOM','CVX',
  'LMT','RTX','NOC',
  'LLY','PFE','JNJ',
  'BTC-USD','ETH-USD',
  'GLD','TLT','COIN',
];

const TICKER_NAMES = {
  'SPY':'S&P 500 ETF','QQQ':'Nasdaq 100 ETF','DIA':'Dow Jones ETF','IWM':'Russell 2000 ETF',
  'AAPL':'Apple Inc.','MSFT':'Microsoft Corp.','GOOGL':'Alphabet Inc.','AMZN':'Amazon.com',
  'META':'Meta Platforms','NVDA':'NVIDIA Corp.','TSLA':'Tesla Inc.','PLTR':'Palantir',
  'JPM':'JPMorgan Chase','BAC':'Bank of America','GS':'Goldman Sachs',
  'XOM':'Exxon Mobil','CVX':'Chevron Corp.',
  'LMT':'Lockheed Martin','RTX':'RTX Corp.','NOC':'Northrop Grumman',
  'LLY':'Eli Lilly','PFE':'Pfizer Inc.','JNJ':'Johnson & Johnson',
  'BTC-USD':'Bitcoin','ETH-USD':'Ethereum',
  'GLD':'Gold ETF','TLT':'20yr Treasury ETF','COIN':'Coinbase Global',
};

async function fetchQuote(symbol) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d&includePrePost=false`;
  const r = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; PolitiSignal/1.0)',
      'Accept': 'application/json',
    },
    cf: { cacheTtl: 60, cacheEverything: true },
  });
  if (!r.ok) return null;
  const data = await r.json();
  const result = data?.chart?.result?.[0];
  if (!result) return null;

  const closes = result.indicators?.quote?.[0]?.close?.filter(v => v != null);
  if (!closes || closes.length < 2) return null;

  const curr = closes[closes.length - 1];
  const prev = closes[closes.length - 2];
  if (!curr || !prev || prev <= 0) return null;

  const displayName = result.meta?.longName || result.meta?.shortName || TICKER_NAMES[symbol] || symbol;

  return {
    price: Math.round(curr * 10000) / 10000,
    change_pct: Math.round((curr - prev) / prev * 10000) / 100,
    name: displayName,
    _updated: new Date().toISOString(),
  };
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const tickerParam = url.searchParams.get('tickers');
  const tickers = tickerParam ? tickerParam.split(',').slice(0, 30) : DEFAULT_TICKERS;

  // Fetch all in parallel
  const results = await Promise.allSettled(tickers.map(t => fetchQuote(t)));

  const prices = {};
  tickers.forEach((ticker, i) => {
    if (results[i].status === 'fulfilled' && results[i].value) {
      // Store with normalized key (BTC-USD → BTC-USD, but also BTC for legacy)
      prices[ticker] = results[i].value;
      // Also add short key for crypto
      if (ticker.endsWith('-USD')) {
        prices[ticker.replace('-USD', '')] = results[i].value;
      }
    }
  });

  return new Response(JSON.stringify(prices), {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=60, s-maxage=60',
    },
  });
}
