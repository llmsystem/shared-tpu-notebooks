# TPU budget verdict through December 15, 2026

Updated October 8, 2026. Plan: **120 students, $150 each, $2,000 hosting reserve**, from the original **$25,000** credit pool.

## Existing billing used in the estimate

The [GCP project billing report](https://console.cloud.google.com/billing/01F962-E9B263-743AEC/reports;timeRange=YEAR_TO_DATE;grouping=GROUP_BY_SKU;credits=FEE_UTILIZATION_OFFSET,COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE,COMMITTED_USAGE_DISCOUNT,FREE_TIER,SUSTAINED_USAGE_DISCOUNT,RESELLER_MARGIN,SUBSCRIPTION_BENEFIT,CREDIT_TYPE_UNSPECIFIED;negotiatedSavings=false;projects=llm-systems-projects?project=llm-systems-projects) for `llm-systems-projects`, viewed October 8 with **Year to date → Group by SKU → Savings (None)**, shows **$77.49 before credits**:

| Observed charge | Usage | USD |
|---|---|---:|
| TPU v5e | 8.16 chip-hours | 9.79 |
| GKE TPU premium | 6.83 chip-hours | 1.15 |
| Balanced persistent disks | 116.42 GiB-months | 12.82 |
| Other shared costs | Includes cluster $19.77 over 197.69 hours, monitoring $8.31, CPU, memory and networking | 53.73 |
| **Total** | | **77.49** |

At the same inspection, Hub showed approximately **6.5 tracked notebook-hours / $8.78 at the old $1.35 rate**. Hub records successful notebook sessions; GCP also charges shared infrastructure and TPU node time outside those sessions. These totals have different coverage; their ratio is not an hourly TPU price.

## Hosting calculation

Using the recorded billing above and approximately **1,642.73 hours remaining** from October 8 through the end of December 15:

- Storage: 127 × 32 GiB (120 students, six staff, one Hub volume) × ($12.82 / 116.42 GiB-months) × (1,642.73 / 730) = **$1,007.07**.
- Other shared costs: ($53.73 / 197.69 observed cluster-hours) × 1,642.73 = **$446.48**.
- Hosting baseline including all recorded spend: $77.49 + $1,007.07 + $446.48 = **$1,531.03** before rounding the components, approximately **$1,531**.

The **$2,000 reserve includes the $77.49 already recorded**, leaving about **$469** above this baseline. This assumes all home disks are provisioned for the remaining period and shared costs continue at their observed rate. Future TPU sessions are additional; monitoring and networking may grow with class activity.

## Updated student computation rate and allocation

Use **$1.40 per tracked chip-hour**, as requested: [Cloud TPU pricing](https://cloud.google.com/tpu/pricing) lists $1.20 for on-demand v5e in us-west4, plus the [GKE TPU premium](https://cloud.google.com/kubernetes-engine/pricing#autopilot-workloads-that-select-specific-hardware) of $0.168945 with the region selector set to Las Vegas (us-west4), totaling $1.368945. The $1.40 budget rate includes about a 2.3% margin above that listed price. The previous $1.35 rate was approximately 1.4% low. Repository defaults, local `config.env`, and the deployed Hub now use $1.40.

| Calculation | Result |
|---|---:|
| Per-student tracked allowance: $150 / $1.40 | **107.14 hours** |
| Total tracked allowance: 120 × 107.14286 hours | **12,857.14 chip-hours** |
| Student allocation: 120 × $150 | **$18,000** |
| Hosting and overhead reserve, including recorded spend | **$2,000** |
| Total planned allocation | **$20,000** |
| Unallocated margin: $25,000 − $20,000 | **$5,000** |

**Verdict:** retain **$150 per student and the $2,000 reserve**. The plan fits within $25,000 under these assumptions. The allowance is all-time, so previously tracked hours reduce each student's remaining hours; changing the rate reprices past tracked sessions. Individual overrides and admin exemptions remain effective. Hub blocks new starts at the limit but lets an existing session finish. Staff TPU use, startup/cleanup time and growth in shared costs consume the remaining margin. Monitor gross GCP costs with **Savings (None)**. Other projects drawing from the credit pool and prior spending outside this report are excluded.

**Deployment:** `make hub` completed successfully on October 8 (Helm release `hub`, revision 21, status `deployed`). Hub and proxy Pods are running; the live Admin page confirms **$1.40 per TPU chip-hour** and the unchanged **$150 default student budget**. All nine usage-tracker tests passed.
