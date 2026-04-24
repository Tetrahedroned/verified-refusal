# Verified-Refusal Benchmark Report

_Generated 2026-04-24T06:46:39.057676+00:00_

This report measures what it costs to discover ten irreversible-action errors two ways: by letting them execute (the live path) and by catching them at a Verified-Refusal gate. Live costs come from public pricing sources (cited in each test case) and the scenario parameters specified in the benchmark definition. Verified-Refusal costs are measured on this machine with `time.perf_counter`, median of 7 iterations per component.

## System

- Python: 3.12.3
- Platform: Linux-6.17.0-20-generic-x86_64-with-glibc2.39
- CPU: AMD Ryzen 5 PRO 2400G with Radeon Vega Graphics

## Summary

| Metric | Value |
|---|---|
| Total potential live cost | $83,573.60 |
| Total VR cost | $0.00 |
| Cost avoided | $83,573.60 |
| Average gate overhead | 1.58 ms |
| Errors caught | 10/10 |

## Test Results

### Test 1 — API key misconfiguration (OpenAI loop)

**Scenario.** Agent loops 100 OpenAI chat calls; wrong model string routes them to GPT-4 Turbo instead of the intended cheaper model.

**Category.** `external_api_side_effect` (expected `external_api_side_effect`; classifier confidence 0.95)

**Live cost:** $6.00

| Line item | Cost |
|---|---|
| `input_tokens_100x2000_at_$15_per_million` | $3.00 |
| `output_tokens_100x500_at_$60_per_million` | $3.00 |
| **Total** | **$6.00** |

**Assumptions.** 100 iterations × 2,000 input + 500 output tokens. Pricing from https://openai.com/api/pricing. Numbers as specified by benchmark scenario.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.631 ms |
| `scan.py` | 1.46 ms |
| gate check | 0.156 ms |
| **Total overhead** | **2.25 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 2 — Bulk email to wrong recipient list

**Scenario.** Filter bug causes 50,000 unsubscribed users to receive a transactional email instead of 50 opted-in users.

**Category.** `message_delivery` (expected `message_delivery`; classifier confidence 0.90)

**Live cost:** $30.00

| Line item | Cost |
|---|---|
| `emails_50000_at_$0.0006` | $30.00 |
| **Total** | **$30.00** |

**Assumptions.** SendGrid Essentials tier: $0.0006/email beyond free tier. Source: https://sendgrid.com/pricing/. CAN-SPAM risk + deliverability damage NOT priced; figure is therefore conservative.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.648 ms |
| `scan.py` | 1.26 ms |
| gate check | 0.154 ms |
| **Total overhead** | **2.07 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 3 — Database write with wrong WHERE clause

**Scenario.** Missing scoping predicate in UPDATE hits all 10,000 user rows instead of a single targeted record.

**Category.** `database_write` (expected `database_write`; classifier confidence 0.95)

**Live cost:** $1,750.00

| Line item | Cost |
|---|---|
| `engineering_recovery_5h_at_$150` | $750.00 |
| `downtime_2h_at_$500` | $1,000.00 |
| **Total** | **$1,750.00** |

**Assumptions.** Recovery: 5 engineering hours at $150/hr blended rate. Downtime: 2 hours at $500/hr small-SaaS impact. Sources: US Bureau of Labor Statistics; $150/hr blended contractor rate is industry-conservative and Conservative small-SaaS estimate — $500/hr. No SLA penalties or customer churn priced in.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.328 ms |
| `scan.py` | 0.772 ms |
| gate check | 0.166 ms |
| **Total overhead** | **1.27 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 4 — Cloud infrastructure over-provisioning

**Scenario.** Typo routes worker provisioning to p3.16xlarge instead of t3.medium; runs undetected for 24 hours.

**Category.** `infrastructure_change` (expected `infrastructure_change`; classifier confidence 0.92)

**Live cost:** $586.52

| Line item | Cost |
|---|---|
| `p3_16xlarge_24h_at_$24.48` | $587.52 |
| `minus_intended_t3_medium_24h_at_$0.0416` | $-1.00 |
| **Total** | **$586.52** |

**Assumptions.** p3.16xlarge on-demand: $24.48/hr. t3.medium on-demand: $0.0416/hr. Source: https://aws.amazon.com/ec2/pricing/on-demand/ (us-east-1). Data transfer charges not priced.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.572 ms |
| `scan.py` | 1.16 ms |
| gate check | 0.170 ms |
| **Total overhead** | **1.90 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 5 — Webhook flood from retry-loop bug

**Scenario.** Retry logic registers the same webhook 500 times; every event fans out 500× to the downstream receiver.

**Category.** `webhook_delivery` (expected `webhook_delivery`; classifier confidence 0.88)

**Live cost:** $998.00

| Line item | Cost |
|---|---|
| `excess_lambda_invocations_499_per_day_for_2_days_at_$1_per_1000` | $998.00 |
| **Total** | **$998.00** |

**Assumptions.** Downstream handler is AWS Lambda at $0.20/million requests + ~$0.0000002/ms. The scenario's simplifying assumption of $0.001/req overstates Lambda alone; in practice the same rate lands with API Gateway + Lambda combined. Sources: https://aws.amazon.com/lambda/pricing/. 1,000 events/day × 499 excess deliveries × $0.001 × 2 days = $998.00. Dead-letter queue and downstream fan-out not priced.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.272 ms |
| `scan.py` | 0.747 ms |
| gate check | 0.135 ms |
| **Total overhead** | **1.15 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 6 — S3 bucket deletion (wrong environment)

**Scenario.** Path resolution bug routes staging delete to the production bucket; 2 TB of customer data destroyed.

**Category.** `infrastructure_change` (expected `infrastructure_change`; classifier confidence 0.92)

**Live cost:** $8,746.08

| Line item | Cost |
|---|---|
| `engineering_recovery_8h_at_$150` | $1,200.00 |
| `s3_standard_2TB_restore_at_$0.023_per_GB` | $46.08 |
| `customer_churn_50_at_$50_MRR` | $2,500.00 |
| `incident_response_baseline` | $5,000.00 |
| **Total** | **$8,746.08** |

**Assumptions.** Recovery: 8 hours at $150/hr. S3 Standard replacement storage: 2,048 GB × $0.023/GB. Customer churn: 5% of 1,000 customers × $50 MRR. Incident response: $5,000 baseline. Sources: https://aws.amazon.com/s3/pricing/, US Bureau of Labor Statistics; $150/hr blended contractor rate is industry-conservative, Conservative SaaS post-incident cost baseline — $5,000.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.251 ms |
| `scan.py` | 0.554 ms |
| gate check | 0.120 ms |
| **Total overhead** | **0.925 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 7 — Payment processor double-charge

**Scenario.** Idempotency key bug charges 1,000 subscription customers twice in the same billing cycle.

**Category.** `financial_transaction` (expected `financial_transaction`; classifier confidence 0.98)

**Live cost:** $54,750.00

| Line item | Cost |
|---|---|
| `erroneous_charges_1000_at_$49` | $49,000.00 |
| `dispute_fees_200_at_$15` | $3,000.00 |
| `refund_processing_fees_1000_at_$0.30` | $300.00 |
| `customer_churn_50_at_$49_MRR` | $2,450.00 |
| **Total** | **$54,750.00** |

**Assumptions.** 1,000 subscribers × $49 avg charge. Stripe dispute fee: $15 × 200 estimated disputes (20% dispute rate). Refund processing: $0.30 per refund. Churn: 5% × $49 MRR. Source: https://stripe.com/pricing. Does not include reputational or regulatory cost.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.261 ms |
| `scan.py` | 0.774 ms |
| gate check | 0.121 ms |
| **Total overhead** | **1.16 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 8 — Rate limit exhaustion (GitHub pagination)

**Scenario.** Pagination loop burns the 5,000/hr authenticated GitHub API quota; all other integrations blocked for 1 hour.

**Category.** `rate_limit_consumption` (expected `rate_limit_consumption`; classifier confidence 0.55)

**Live cost:** $1,800.00

| Line item | Cost |
|---|---|
| `delayed_deployments_3_at_$500_each` | $1,500.00 |
| `debugging_2h_at_$150` | $300.00 |
| **Total** | **$1,800.00** |

**Assumptions.** GitHub API itself is free. Cost is opportunity cost: 3 delayed deployments at $500/ea engineering cost and 2 hours debugging at $150/hr. Sources: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api, US Bureau of Labor Statistics; $150/hr blended contractor rate is industry-conservative.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.544 ms |
| `scan.py` | 1.02 ms |
| gate check | 0.168 ms |
| **Total overhead** | **1.73 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 9 — LLM agent tool-call loop

**Scenario.** Autonomous agent enters a tool-call loop, hitting the search API 200 times before token limit halts the loop.

**Category.** `external_api_side_effect` (expected `external_api_side_effect`; classifier confidence 0.95)

**Live cost:** $7.00

| Line item | Cost |
|---|---|
| `perplexity_searches_200_at_$0.005` | $1.00 |
| `llm_tokens_400k_at_$0.000015` | $6.00 |
| **Total** | **$7.00** |

**Assumptions.** Perplexity: $0.005/search. LLM token spend: 200 calls × 2,000 tokens × $15/million. Sources: https://docs.perplexity.ai/guides/pricing, https://openai.com/api/pricing.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.554 ms |
| `scan.py` | 0.952 ms |
| gate check | 0.193 ms |
| **Total overhead** | **1.70 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

### Test 10 — DNS record deletion (primary domain)

**Scenario.** Regex bug matches production A records instead of staging; deletes primary domain's A record. Site offline until TTL restoration completes.

**Category.** `infrastructure_change` (expected `infrastructure_change`; classifier confidence 0.93)

**Live cost:** $14,900.00

| Line item | Cost |
|---|---|
| `downtime_24h_at_$500` | $12,000.00 |
| `incident_response_6h_at_$150` | $900.00 |
| `seo_impact_estimate` | $2,000.00 |
| **Total** | **$14,900.00** |

**Assumptions.** Assumes 24-hour restoration window (TTL propagation). Downtime cost: $500/hr × 24h. Incident response: 6 eng hours at $150. SEO: conservative $2,000 short-term ranking loss estimate. Sources: US Bureau of Labor Statistics; $150/hr blended contractor rate is industry-conservative, Conservative small-SaaS estimate — $500/hr.

**VR cost:** $0.00

| Component | Time |
|---|---|
| `classify.py` | 0.531 ms |
| `scan.py` | 0.939 ms |
| gate check | 0.156 ms |
| **Total overhead** | **1.63 ms** |

**Result.** Gate triggered: ✓ · Report generated: ✓ · Error caught: ✓

---

## What this means

$83,573.60 of cost would have been realized if these ten errors reached live execution. The same ten errors were caught at the gate for a total of 15.78 ms of CPU time and $0.00 spend, an average of 1.58 ms per action.

The overhead to prove correctness is measured in milliseconds. The cost of discovering the same errors in production is measured in dollars.

## Reproducing

```bash
python3 benchmarks/run_benchmarks.py
```

`benchmarks/results.json` holds the full machine-readable data, including every per-iteration timing.
