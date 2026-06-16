import { useState } from 'react';
import type { DraftRecord } from '@/lib/types';
import { cn } from '@/lib/cn';
import { Edit3, Save, X, Copy, Check, MessageCircle } from 'lucide-react';
import { resolvePhone, hasMappedPhone, whatsappSendUrl } from '@/lib/demoPhones';

export function WhatsAppPreview({
  customer,
  draft,
}: {
  customer: any;
  draft: DraftRecord;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft.message);
  const [savedText, setSavedText] = useState(draft.message);
  const [sent, setSent] = useState(false);
  const [copied, setCopied] = useState(false);

  const phone = resolvePhone(customer?.name, customer?.phone);
  const mapped = hasMappedPhone(customer?.name);

  async function copy() {
    try {
      await navigator.clipboard.writeText(savedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {/* clipboard unavailable */}
  }

  async function sendOnWhatsApp() {
    // Copy as a safety net in case the pre-fill is blocked, then open the chat.
    try {
      await navigator.clipboard.writeText(savedText);
    } catch {/* clipboard unavailable */}
    window.open(whatsappSendUrl(phone, savedText), '_blank', 'noopener,noreferrer');
    setSent(true);
    setTimeout(() => setSent(false), 2500);
  }

  return (
    <div>
      <div className="mx-auto max-w-md">
        <div className="rounded-2xl bg-[#0b1218] border border-border overflow-hidden shadow-lg">
          {/* Status bar */}
          <div className="h-6 bg-black/60 flex items-center justify-center text-[10px] text-text-muted">
            ── Live Preview ──
          </div>
          {/* Header */}
          <div className="px-3 py-2 bg-[#1f2c33] flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-accent/30 flex items-center justify-center text-[12px] text-white">
              {(customer.name || '?').slice(0, 1)}
            </div>
            <div>
              <div className="text-[12px] font-medium text-white">{customer.name}</div>
              <div className="text-[10px] text-text-muted">Online</div>
            </div>
          </div>
          {/* Body */}
          <div className="px-3 py-4 bg-[#0b1218] min-h-[140px]">
            {editing ? (
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                className="w-full bg-[#005c4b]/30 border border-accent/30 text-[13px] text-white px-3 py-2 rounded-md focus:outline-none focus:ring-1 focus:ring-accent resize-none"
                autoFocus
              />
            ) : (
              <div
                className={cn(
                  'inline-block max-w-[88%] bg-[#005c4b] text-white text-[13px] px-3 py-2 rounded-lg rounded-tl-sm leading-relaxed',
                  'shadow-md',
                )}
              >
                {savedText}
                <div className="text-[9px] text-white/60 mt-1 text-right">
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="mt-3 flex flex-wrap gap-2">
          {editing ? (
            <>
              <button
                onClick={() => { setEditing(false); setText(savedText); }}
                className="btn-ghost"
              >
                <X size={13} /> Cancel
              </button>
              <button
                onClick={() => { setSavedText(text); setEditing(false); }}
                className="btn-primary"
              >
                <Save size={13} /> Save
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} className="btn-outline">
                <Edit3 size={13} /> Edit
              </button>
              <button onClick={copy} className="btn-outline">
                {copied ? <Check size={13} className="text-positive" /> : <Copy size={13} />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                onClick={sendOnWhatsApp}
                disabled={!phone}
                className={cn('btn-primary', sent && 'opacity-80')}
                title={
                  phone
                    ? 'Opens WhatsApp Web with the message pre-filled — review, then press Send'
                    : 'No phone number available for this customer'
                }
              >
                {sent ? <Check size={13} /> : <MessageCircle size={13} />}
                {sent ? 'Opened in WhatsApp' : 'Send on WhatsApp'}
              </button>
            </>
          )}
        </div>

        {!mapped && phone && (
          <p className="mt-2 text-[11px] text-text-dim leading-relaxed">
            Note: this customer uses a synthetic demo number, so WhatsApp may show
            “not on WhatsApp”. The message is copied to your clipboard either way.
          </p>
        )}

        {draft.compliance && !draft.compliance.ok && (draft.compliance.ungrounded || []).length > 0 && (
          <div className="mt-3 text-[11px] rounded-md bg-warning/10 border border-warning/30 text-warning px-3 py-2 leading-relaxed">
            Compliance validator stripped numbers not present in source context:&nbsp;
            <span className="font-mono">{(draft.compliance.ungrounded || []).join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
}
