/**
 * Cloudflare Pages Function — Stripe Subscription Verification
 *
 * POST /api/verify
 *   Body: { email: "customer@example.com" }
 *
 * Checks Stripe for an active subscription matching the email.
 * Returns: { ok: true, plan: "trader"|"elite" } or { ok: false, plan: null }
 *
 * Required Cloudflare Pages secret:
 *   STRIPE_SECRET_KEY — restricted key with customers:read + subscriptions:read
 */

export async function onRequestPost(context) {
  const STRIPE_KEY = context.env.STRIPE_SECRET_KEY;
  if (!STRIPE_KEY) {
    return json({ ok: false, error: 'Verification not configured' }, 503);
  }

  let email;
  try {
    const body = await context.request.json();
    email = (body.email || '').trim().toLowerCase();
  } catch {
    return json({ ok: false, error: 'Invalid request body' }, 400);
  }

  if (!email || !email.includes('@')) {
    return json({ ok: false, error: 'Valid email required' }, 400);
  }

  try {
    // Look up customer(s) by email — one person may have signed up twice
    const custRes = await fetch(
      `https://api.stripe.com/v1/customers?email=${encodeURIComponent(email)}&limit=5`,
      { headers: { Authorization: `Bearer ${STRIPE_KEY}` } }
    );
    if (!custRes.ok) throw new Error(`Stripe customers API: ${custRes.status}`);
    const custData = await custRes.json();
    const customers = custData.data || [];

    if (!customers.length) {
      return json({ ok: false, plan: null, message: 'No account found for that email' });
    }

    // Check active subscriptions across all matching customers
    let bestPlan = null;
    for (const customer of customers) {
      for (const status of ['active', 'trialing']) {
        const subRes = await fetch(
          `https://api.stripe.com/v1/subscriptions?customer=${customer.id}&status=${status}&limit=10`,
          { headers: { Authorization: `Bearer ${STRIPE_KEY}` } }
        );
        if (!subRes.ok) continue;
        const subData = await subRes.json();
        const subs = subData.data || [];

        for (const sub of subs) {
          for (const item of sub.items.data) {
            // Determine plan by price amount (cents)
            // $49/mo or more = Elite, $19/mo or more = Trader
            const amount = item.price?.unit_amount || 0;
            if (amount >= 4900) {
              bestPlan = 'elite';
              break;
            } else if (amount >= 1900) {
              if (bestPlan !== 'elite') bestPlan = 'trader';
            } else if (subs.length > 0 && !bestPlan) {
              // Any active sub with unknown price = trader minimum
              bestPlan = 'trader';
            }
          }
          if (bestPlan === 'elite') break;
        }
        if (bestPlan === 'elite') break;
      }
      if (bestPlan === 'elite') break;
    }

    if (bestPlan) {
      return json({ ok: true, plan: bestPlan });
    }

    return json({ ok: false, plan: null, message: 'No active subscription found for that email' });

  } catch (e) {
    console.error('Verify error:', e);
    return json({ ok: false, error: 'Verification service unavailable' }, 502);
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders() });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders() },
  });
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}
