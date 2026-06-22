# Customer Financial History — Salary, CIBIL & Loan Records (Reference Knowledge Base)

> Companion to the customer database in `backend/data` (SQLite: customers, accounts,
> transactions, holdings, interactions). This document defines how 5-year salary history
> maps to a CIBIL score, and the detailed loan-history model the RM Copilot reasons over.

## 1. Five-year salary history → CIBIL score

We derive a credit profile from five years of salary credits plus repayment behaviour.

### Inputs we read per customer
- **Monthly salary credits** for the last 60 months (trend, stability, gaps).
- **Salary growth rate** year over year (a steady rise signals improving repayment capacity).
- **Average bank balance (6m / 12m)** and balance buffer vs monthly outflow.
- **Existing EMIs** and total obligations (for FOIR/DTI).
- **Repayment track record** (DPD history) on all live and closed loans.

### CIBIL score bands and what they mean
| Band | Range | Interpretation | RM action |
|---|---|---|---|
| Excellent | 800–900 | Lowest risk; best pricing | Offer top-tier rates, pre-approved limits |
| Very good | 750–799 | Strong; standard approvals | Cross-sell confidently |
| Good | 700–749 | Acceptable; minor conditions | Position with co-applicant if needed |
| Fair | 650–699 | Elevated risk; tighter terms | Smaller ticket, higher spread |
| Poor | 300–649 | High risk; likely decline | Secured products, credit-builder steps |
| New-to-credit | NA/NH | No history | Entry products, on-us salary advantage |

### Simplified scoring methodology (transparent, explainable)
- Repayment history (DPD, defaults): **35%**
- Credit utilisation: **30%**
- Credit age / salary tenure: **15%**
- Credit mix (secured + unsecured): **10%**
- Recent enquiries: **10%**

A 5-year stable-and-rising salary with 0 DPD and <30% utilisation typically maps to **760–820**.

## 2. Detailed loan-product histories the RM can reference

### Personal loan
- **Purpose:** unsecured, any end-use; fastest to disburse.
- **Ticket:** ₹50k – ₹40L. **Tenure:** 12–60 months. **Rate:** 10.5%–24% APR.
- **History fields:** sanction amount, outstanding, EMI, DPD, prepayments, top-up eligibility.
- **Signal for RM:** salary customer with 0 DPD and no live PL → strong cross-sell.

### Home loan
- **Purpose:** purchase/construction/renovation; secured by property.
- **Ticket:** ₹5L – ₹5Cr+. **Tenure:** up to 30 years. **Rate:** 8.35%–9.75%. **LTV:** up to 90%.
- **History fields:** property value, LTV, balance, ROI type (fixed/floating), tax benefits used.
- **Signal:** EBLR reset or rate drop → balance-transfer / top-up conversation.

### Credit card
- **Purpose:** revolving unsecured credit; rewards + EMI conversion.
- **Limit:** ~3x monthly salary (indicative). **Revolving APR:** 30%–46%.
- **History fields:** limit, utilisation %, min-due behaviour, EMI conversions, reward tier.
- **Signal:** high utilisation + on-time payer → limit upgrade or PL balance-consolidation.

### Vehicle loan
- **Purpose:** new/used car or two-wheeler; secured by the vehicle (hypothecation).
- **Ticket:** ₹50k – ₹50L. **Tenure:** 12–84 months. **Rate:** 8.75%–17%. **LTV:** up to 85–90%.
- **History fields:** asset, LTV, balance, insurance status, prepayment record.
- **Signal:** loan near closure + good record → pre-approved next-vehicle or top-up.

## 3. Ease of use — how the RM consumes this

- Every customer record links salary trend, CIBIL band, and live/closed loans in one view.
- The agent surfaces the **single most actionable signal** (e.g. "no active loan, salary
  rising 9% YoY, 0 DPD") and the recommended product, so the RM acts in one glance.
- Opportunity sizing uses these histories (e.g. personal loan ≈ up to 10× monthly salary,
  capped; home loan ≈ up to 60×) to prioritise calls by expected value.

## 4. Data dictionary (fields available per customer)

| Field | Meaning |
|---|---|
| monthly_income | Latest monthly salary credit |
| salary_growth_yoy | Year-over-year salary growth |
| avg_balance_6m | Average balance, trailing 6 months |
| cibil_band | Excellent / Very good / Good / Fair / Poor / New-to-credit |
| foir | Fixed obligations to income ratio (EMIs ÷ income) |
| live_loans | Active personal / home / vehicle / card facilities |
| dpd_history | Days-past-due record across facilities |
| prepayments | Count and amount of prior prepayments |
| top_up_eligible | Whether a top-up is pre-qualified |

## 5. Worked examples (aligned to seed personas)

- **Priya Sharma (HNW, Mumbai):** salary ~₹3.2L/m rising steadily, strong 6m balance, no
  active personal loan → CIBIL band Very good/Excellent → prime Personal Loan + Home top-up.
- **Retention profile (salary-credit slowdown):** salary inflow dipping, balance buffer
  thinning → churn-risk flag → offer overdraft / restructuring before a missed EMI.
