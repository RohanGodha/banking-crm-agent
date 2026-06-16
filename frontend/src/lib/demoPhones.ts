/**
 * Demo phone resolution for "Send on WhatsApp".
 *
 * Hero customers in the seed data carry synthetic (fake) phone numbers, so a
 * real WhatsApp chat won't open for them. For live demos we map specific
 * customers to real test numbers via the VITE_DEMO_PHONES env var (kept out of
 * the public repo in .env.local / Vercel env), e.g.:
 *
 *   VITE_DEMO_PHONES={"Priya":"917037148039","Ananya":"919337519698"}
 *
 * Keys match the customer's first name (case-insensitive); full name also works.
 */

type PhoneMap = Record<string, string>;

let cached: PhoneMap | null = null;

function loadMap(): PhoneMap {
  if (cached) return cached;
  cached = {};
  const raw = import.meta.env.VITE_DEMO_PHONES as string | undefined;
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      for (const [k, v] of Object.entries(parsed)) {
        cached[k.trim().toLowerCase()] = String(v).replace(/\D/g, '');
      }
    } catch {
      /* malformed env — ignore, fall back to customer's own phone */
    }
  }
  return cached;
}

/**
 * Resolve a sendable WhatsApp number (digits only, country code included).
 * Priority: env mapping by name → the customer's own phone (digits).
 * Returns '' if nothing usable is available.
 */
export function resolvePhone(name?: string | null, fallbackPhone?: string | null): string {
  const map = loadMap();
  if (name) {
    const lower = name.trim().toLowerCase();
    const first = lower.split(/\s+/)[0];
    if (first && map[first]) return map[first];
    if (map[lower]) return map[lower];
  }
  return (fallbackPhone || '').replace(/\D/g, '');
}

/** True when a real (mapped) number exists for this customer. */
export function hasMappedPhone(name?: string | null): boolean {
  const map = loadMap();
  if (!name) return false;
  const lower = name.trim().toLowerCase();
  return Boolean(map[lower] || map[lower.split(/\s+/)[0]]);
}

/**
 * Build a WhatsApp Web "send" URL that opens the chat with the message
 * pre-filled. If the user is logged into WhatsApp Web in the same browser it
 * lands directly in the conversation (they still press Send — human in the loop).
 */
export function whatsappSendUrl(phone: string, text: string): string {
  const q = new URLSearchParams();
  if (phone) q.set('phone', phone);
  q.set('text', text);
  return `https://web.whatsapp.com/send?${q.toString()}`;
}
