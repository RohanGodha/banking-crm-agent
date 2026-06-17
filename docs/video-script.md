# RM Copilot — Demo Video Script (~7 min)

Beat-by-beat: **kab**, **kya dikhana hai (screen)**, **kya bolna hai (narration)**.
Narration Hinglish me hai — apne comfort ke hisaab se English/Hindi adjust kar lena.

---

## Recording se pehle (prep checklist)

- [ ] Backend warm karo: `https://banking-crm-agent.onrender.com/healthz` ek baar khol lo (free tier cold start ~50s — warna pehli query slow lagegi).
- [ ] **Groq/Gemini quota fresh ho** — recording se thodi der pehle 10-15 test queries mat maaro, warna drafts mock pe gir sakte hain. Ho sake to subah/fresh window me record karo.
- [ ] WhatsApp send dikhana hai to:
      - **Local** (safest): `frontend/.env.local` me numbers already set hain → `npm run dev`. Apna WhatsApp Web us browser me logged-in rakho.
      - **Live**: Vercel me `VITE_DEMO_PHONES` env var set + redeploy.
- [ ] Browser zoom 100%, screen clean (notifications off), 1080p recording.
- [ ] Theme **dark** se start karna (default), beech me light dikhayenge.
- [ ] Do tabs ready: ek desktop view, ek mobile/responsive view (DevTools device toolbar) — end me mobile dikhane ke liye.

---

## Beat sheet

| Time | Screen — kya dikhana hai | Narration — kya bolna hai |
|---|---|---|
| **0:00–0:30** | Login page (theme toggle top-right dikhe). | "Hi, main Rohan. Ye hai **RM Copilot** — ek agentic AI jo banking Relationship Manager ki rozaana ki sabse badi problem solve karta hai: *aaj kis customer ko call karun, aur kya bolun?* React + FastAPI pe bana hai, real LLMs aur RAG ke saath, pura free-tier pe deployed." |
| **0:30–1:00** | Password `shared` daalo → Dashboard khulta hai. 3-pane layout pe ungli ghumao (left: chats, center: copilot, right: candidates). | "Login ke baad ye 3-pane workspace — left me conversations, center me copilot chat, right me live candidates. Sab kuch streaming hai, aur har step transparent." |
| **1:00–1:20** | Header me **theme toggle** (sun/moon) dabao → light mode → wapas dark. | "Pehle ek quick UI note — full **light/dark theme**, preference save hoti hai. Aur UI 100% mobile-responsive hai, woh end me dikhata hoon." |
| **1:20–3:10** | Center chat me **Scenario A** type karo:<br>*"Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages."*<br>Enter. **Live D3 pipeline** chalte hue dikhao. | "Ab asli kaam. Main plain language me poochta hoon… aur dekhiye — ye sirf chat nahi hai. Niche ye **live pipeline** dikha raha hai agent ka actual reasoning: Intent → Plan → Retrieve → Critic → Synthesize → Draft." |
| **2:00–2:30** | "Agent reasoning" trace panel expand karo. Steps point karo: planner, tool calls, `source: sqlite`, RAG `chroma+bm25`, critic. | "Ye reasoning chhupa hua nahi hai. Planner ne task ko **5 typed tool steps** me toda. Har tool result pe source aur latency tagged hai — ye BFSI audit ke liye zaroori hai. Retrieval **hybrid RAG** hai — dense embeddings plus BM25." |
| **2:30–3:10** | Right pane me **candidates** aate hue dikhao (composite score ring). Top candidate (e.g. **Priya**) point karo. | "Right side me candidates real-time rank ho ke aate hain — **composite score** = value + propensity. Ye numbers hardcoded nahi hain, actual scoring se aate hain. Top pe Priya — high value, high conversion likelihood." |
| **3:10–4:00** | Kisi candidate pe click → **Customer 360 drawer**. Score Breakdown chart, rationale, fir **WhatsApp Draft** section. | "Customer pe click karta hoon — pura **360 view**. Ye **score breakdown** har feature ka contribution dikhata hai — koi black box nahi. Aur niche ye **WhatsApp draft**, LLM se generated, customer ke real signals pe grounded." |
| **4:00–4:30** | **Compliance OK** badge point karo. Fir **Send on WhatsApp** dabao → WhatsApp Web pre-filled khulta hai. | "Dekhiye **Compliance OK** — ek validator har number check karta hai; jo number source data me nahi hai woh strip ho jaata hai. Ye generic LLM drafts ka sabse bada BFSI risk solve karta hai. Aur **Send on WhatsApp** — message pre-filled aa gaya, RM review karke bhejta hai. Human-in-the-loop." |
| **4:30–5:20** | Wapas chat. **Scenario B** (same session):<br>*"Now narrow it to Bangalore customers and make the messages warmer."* | "Ab **stateful refinement**. Main pehle wali query repeat nahi kar raha — sirf bolta hoon 'ab sirf Bangalore, aur warmer tone'. Agent context yaad rakhta hai…" (candidates update → sab Bangalore) "…aur dekhiye candidates ab sirf Bangalore ke, drafts dobara generate, warmer tone me." |
| **5:20–6:10** | **Scenario C** (naya):<br>*"Show me customers with salary-credit slowdown — what should we offer them."* | "Ye sabse important — proof ki ye reasoning hai, hardcoding nahi. Salary slowdown ek **retention** signal hai. Dekhiye — agent ne khud personal loan nahi, **overdraft** product choose kiya, aur risk-wale customers ko surface kiya, churn-risk badge ke saath." |
| **6:10–6:35** | Ek out-of-scope query: *"Write a poem about Mumbai rain"* → polite decline. Fir ek FAQ: *"What products can you recommend?"* | "Guardrails bhi hain — banking ke bahar ka kuch poochho to politely mana karta hai. Aur capability questions ka grounded jawab deta hai, koi hallucination nahi." |
| **6:35–6:55** | **Guide** button kholo → capabilities, products, 50 FAQs, live status strip. | "Ek **Guide panel** bhi — saari capabilities, products, 50 real FAQs, aur live system status: kaunsa LLM, data source, RAG mode active hai." |
| **6:55–7:15** | DevTools device toolbar on → mobile view. Bottom tab bar (Chats/Copilot/Candidates) switch karke dikhao. Theme toggle bhi. | "Aur ye sab **100% mobile responsive** — bottom navigation se panes switch hote hain, full theme support. RM apne phone pe field me use kar sakta hai." |
| **7:15–7:40** | Architecture diagram (README) ya bas closing slide. | "Architecture: hexagonal ports — Databricks↔SQLite failover, Gemini↔Groq↔Mock routing, hybrid RAG, compliance validator, full SSE streaming, custom trace observability. Sab free-tier pe. Thank you — repo aur live link description me hain." |

---

## Quick reference — exact queries (copy-paste)

1. `Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.`
2. `Now narrow it to Bangalore customers and make the messages warmer.`  *(same session)*
3. `Show me customers with salary-credit slowdown — what should we offer them.`
4. `Write a poem about Mumbai rain.`  *(guardrail)*
5. `What products can you recommend?`  *(FAQ)*

## Agar kuch galat ho jaaye (fallbacks)

- **Drafts "mock" dikhein** → Groq quota khatam. Recording rok do, 5-10 min baad fresh try karo, ya pehle se `/tools/generate_whatsapp_message` ek baar hit karke confirm karo `llm_route=groq`.
- **Pehli query slow** → backend cold tha; ek dummy query pehle chala ke warm kar lo, fir record karo.
- **WhatsApp "not on WhatsApp"** → us customer ka number `VITE_DEMO_PHONES` me map nahi hai; mapped customer (Priya/Aarav/Ananya/Vikram/Neha) use karo.
- **Backend down** → README me likha mock fallback; worst case local pe `npm run dev` + `uvicorn` se record kar lo.

## Tips
- Bolne ki speed thodi slow rakho; har scenario ke baad 1-2 sec pause (editing me kaam aata hai).
- Mouse se actively point karo jab "source", "compliance OK", "composite score" bol rahe ho.
- Total target: **6–8 min**. Assignment 5–10 min maangta hai — sweet spot 7 min.
