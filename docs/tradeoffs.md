# Trade-offs and limitations

Honest engineering trade-offs documented here for the README and the demo.

## What was deliberately not built

| Skipped                                        | Why                                                              | What we'd add in production                                     |
| ---------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------- |
| Trained ML lead-scoring model                  | Reproducibility + explainability mattered more than 2-3% AUROC   | Gradient-boosted scorer behind same `Scorer` interface, with periodic offline labelling                            |
| Real WhatsApp send                             | Out of scope; requires Twilio business account                   | `MessageChannel` port with adapters for Twilio, MoEngage, in-house gateway. Add idempotency + rate-limiting        |
| Multi-tenant / SSO                             | Single-RM demo                                                   | JWT + refresh, per-tenant data isolation, row-level Databricks ACLs                                                |
| Distributed tracing (OTLP)                     | Free tier doesn't include a backend                              | Honeycomb free tier or Grafana Cloud free; same `TraceEvent` payload, additional exporter                          |
| Mosaic AI Vector Search inside Databricks      | Not yet free                                                     | Drop local Chroma when Databricks Vector Search moves to free tier                                                 |
| Background re-embedding pipeline               | Not needed at 500 customers                                      | Airflow / Databricks Workflow to refresh embeddings nightly                                                        |
| Per-user prompt tuning / preferences           | Single-RM demo                                                   | `rm_preferences` table; tone defaults; suggested-time defaults                                                     |

## Known limitations

- **Synthetic data:** 500 Faker customers + 5 hand-crafted hero personas. The RAG corpus is small; production would have thousands of real interaction summaries.
- **Heuristic scorer drift:** weights in `weights.yaml` are hand-tuned. A production system would A/B against a trained baseline.
- **Critic is heuristic, not LLM-powered:** to save tokens. Upgrading to an LLM Critic for hard cases is a one-line change in `nodes/critic.py`.
- **Render free tier:** cold start ~50 s, 512 MB RAM, sleeps after 15 min idle. Self-ping + cron-job.org mitigate but a paid tier removes the risk.
- **Databricks Free Edition:** serverless warehouse has cold-start latency (~30 s). The `FailoverSource` masks this; the trade-off is the trace will read `sqlite(failover)` until the warehouse warms.
- **No real-time SQL streaming:** all warehouse reads are batch. For live RM dashboards we'd add a subscription mechanism (Databricks Streaming Tables).
- **Compliance validator is conservative:** it strips ungrounded numbers rather than regenerating. In production we'd add a one-shot regen pass before stripping.

## Architectural debts logged for follow-up

- **`agent_traces` table grows unbounded** — add a TTL job (e.g., keep last 30 days).
- **`tool_cache` not yet wired into tools** — schema exists, the `cache_key` strategy is a future PR.
- **SSE retry on the client** — we currently surface an error banner on connection loss; should auto-retry with exponential backoff.
- **No telemetry on the LLM router** — we should record `route_used` aggregates so we can quantify how often Gemini vs Groq vs Mock served traffic.
