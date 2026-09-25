# Reference cases

Fourteen cases validate the engine against public court calculators to the cent. Cases 01 to 10 were produced in JuriscalcWeb (the TJDFT's public calculator) by browser automation; 11 to 14 in Dr. Calc (a commercial service used by Brazilian litigators). Every value below is asserted in `tests/engine/`; if a test breaks, either the ingested indices changed retroactively (the ingestion detects that and stops) or the engine regressed. Party names and case numbers of the originating matters are not reproduced; the amounts are not identifying.

Unless stated, the adjustment is the "tjdft" composite (INPC until 08/2024, IPCA from 09/2024), `adjust_until` = 2026-04 and `final_date` = 22/05/2026.

## Conventions decoded

| # | Convention | Where it came from |
|---|---|---|
| 1 | Adjustment by full months: an amount dated any day of month M gets the whole change of M. | case 01 |
| 2 | Interest period `[start, end)`: the first day counts, the end day does not (15/05 to 22/05 = 7 days). | case 01 |
| 3 | Pro rata by calendar days over the real days of the month, including the regime switch (Aug/2024 = 29/31 at 1 % + 2/31 of the Legal Rate). | cases 03, 04 |
| 4 | Legal interest timeline: 0.5 % until 10/01/2003, 1 % until 29/08/2024, Legal Rate from 30/08/2024. | cases 03, 06 |
| 5 | Fixed percentage counts inclusive calendar months of both edge months (Mar/2020 to May/2026 = 75). | case 02 |
| 6 | Interest never precedes the debt: an installment later than the configured start accrues from its own date. | case 10 |
| 7 | The TJSP table switches to IPCA-15 one month before the TJDFT switch (Aug/2024), and "table of month M" means indices up to M-1. | case 11 |
| 8 | Dated court fees and discounts are adjusted from their own date, without interest. | case 12 |
| 9 | A late fine is a percentage of each installment's adjusted amount, rounded per line; awarded fees may exclude it from their base. | case 14 |
| 10 | Every total is the sum of the rounded lines, never the rounding of a raw sum. | case 05 |

## Cases

| # | Scenario | Key parameters | Expected |
|---|---|---|---|
| 01 | Awarded fees over an updated economic benefit | 134,000.00 on 02/03/2022; Legal Rate from 15/05/2026 | adjusted 162,290.65 (factor 21.11 %), interest 0.044776 % = 72.67, total 162,363.32, fees 10 % = 16,236.33 |
| 02 | Long fixed interest | 10,000.00 on 15/03/2020; 1 % fixed from 15/03/2020 | adjusted 14,253.07; 75 months = 75 %; interest 10,689.80; total 24,942.87 |
| 03 | Legal interest across the Law 14,905 switch | 10,000.00 on 15/03/2020; legal from 15/03/2020 | 67.427077 %; interest 9,610.43; total 23,863.50 |
| 04 | Multiple installments, interest from service | 1,850 (03/2022), 1,850 (04/2022), 1,920 (11/2022); legal from 01/06/2023 | 28.878689 %; lines 2,887.63 / 2,839.08 / 2,907.35; total 8,634.06 |
| 05 | Case 01 + art. 523 surcharges | fine 10 %, fees 10 % | fine 16,236.33, fees 16,236.33, creditor 178,599.65, total 194,835.98 (JuriscalcWeb shows .64/.97: float64 aggregation that does not add up to its own lines) |
| 06 | Three interest eras | 5,000.00 on 15/05/2001; legal from 15/05/2001 | adjusted 22,717.01; engine 283.491593 %; JuriscalcWeb 283.427077 % (it leaves two days of Jan/2003 without interest; reproduced with the 2/31 hole: 64,386.14 / 87,103.15); engine 64,400.80 / 87,117.81 |
| 07 | No interest | 10,000.00 on 20/08/2015 | 17,419.84 |
| 08 | Pure INPC | 7,500.00 on 10/07/2021, index inpc | 9,760.68; JuriscalcWeb applies 1 % by calendar months with this index (59 % = 5,758.80 / 15,519.48), reproducible with the fixed regime; the engine keeps the Legal Rate timeline |
| 09 | Fixed interest from service, two installments | 3,000 (06/2022), 3,000 (09/2022); 1 % from 15/02/2023 | 40 months; 4,927.55 / 4,942.07; total 9,869.62 |
| 10 | Legal interest from each amount's date | 2,000 (10/01/2023), 2,500 (15/07/2023), 3,000 (05/10/2024) | 33.588367 % / 27.427077 % / 13.137057 %; totals 3,105.85 / 3,606.34 / 3,684.65; sum 10,396.84 |
| 11 | TJSP practical table | index tjsp, adjust_until 2026-05, no interest | 1,000 (03/2020) = 1,433.87; 2,500 (01/2025) = 2,689.21; boundary 07/2024..12/2024 = 1,098.24 / 1,095.39 / 1,093.32 / 1,091.90 / 1,086.03 / 1,079.34; 1,000 (05/1996) = 6,039.23 (Dr. Calc 6,039.21: its table publishes 6-decimal factors) |
| 12 | Dated entries | tjsp, no interest, until 2026-05; 10,000 (15/01/2023), 2,000 (10/06/2024); court fee 500 (20/03/2025); discount 300 (10/01/2026) | 11,694.55 + 2,201.97 = 13,896.52; fee 530.72; discount 309.07; total 14,118.17 |
| 13 | Fees as the claim being enforced | case 01 + awarded fees 10 % as the claim + art. 523 10/10 | enforceable 16,236.33; fine and fees 1,623.63 each; creditor 17,859.96; total 19,483.59 |
| 14 | Late fine and fees without the fine | inpc, until 2026-01, fixed 1 % ending 31/01/2026, final 04/03/2026; 6 installments (107,000.00 on 29/09/2019 and five small ones); fine 10 %; fees 30 % net of the fine; 11 court fees; 4 discounts | adjusted 152,795.85; interest 117,050.13; fine 15,279.59; gross 285,125.57; fee base 269,845.98; fees 80,953.79; court fees 15,054.52; discounts 354,817.01; total 26,316.87 |

Internal-consistency cases without an external benchmark: the deductions cascade (penalty 25 % of the gross, two fixed deductions, 5 % awarded fees over the net, art. 523 over the enforceable amount: total 150,286.59), contract fees (informative, no total changes), title fees (they add to the enforceable amount and stay out of the creditor's amount).

## Precision

JuriscalcWeb computes in float64 (JavaScript), so its 6th decimal oscillates by ±0.000001 between scenarios. The engine is exact `Decimal`; the guaranteed parity is to the cent in money and ±0.000001 in displayed percentages. Where the engine deliberately differs (cases 06 and 08), the divergence is documented, reproducible and in the creditor's favour or a matter of legal choice, never an approximation.
