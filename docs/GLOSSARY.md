# Glossary

Brazilian legal and financial terms behind the English identifiers of this repository. The Portuguese term is what a Brazilian lawyer, judgment or court calculator says; the English column is what the code says.

## The calculation

| Portuguese | In the code | Meaning |
|---|---|---|
| correção monetária | monetary adjustment, `adjusted`, `factor` | Inflation adjustment of an amount by an official monthly index, applied by full months from the month of the amount until `adjust_until`. |
| competência | month (`YYYY-MM`) | The reference month of an index value or of an amount. |
| atualização até | `adjust_until` | The last month whose index is applied. In court practice "table of month M" means indices up to month M-1. |
| juros de mora | default interest, `interest` | Simple interest for the delay, over the adjusted amount (CMN Resolution 5,171/2024, art. 7). |
| juros legais | `interest_regime = "legal"` | Civil Code art. 406: 0.5 % per month until 10/01/2003, 1 % per month until 29/08/2024, then the Legal Rate. |
| Taxa Legal | Legal Rate, series `legal_rate` (SGS 29543) | The statutory monthly rate published by the central bank since Law 14,905/2024 (Selic minus IPCA, floored at zero). |
| percentual fixo | `interest_regime = "fixed"`, `fixed_monthly_rate` | A rate set by the contract or the decision, counted in inclusive calendar months (JuriscalcWeb convention). |
| termo inicial dos juros | `interest_start` | The date interest starts: service of process (citação), final judgment (trânsito em julgado) or the harmful event. Never before the amount's own date. |
| data final do cálculo | `final_date` | The date the statement is drawn up; the end of the interest count. |
| memória de cálculo / demonstrativo | calculation statement | The itemised document that accompanies the enforcement petition (CPC art. 524, I). |
| valor original / singelo | `amount`, "original" | The nominal amount on its date, before any adjustment. |

## Indices and courts

| Portuguese | In the code | Meaning |
|---|---|---|
| INPC, IPCA, IPCA-15 | `inpc`, `ipca`, `ipca15` | Consumer price indices of IBGE, the national statistics office. |
| IGP-M, IGP-DI | `igpm`, `igpdi` | General price indices of FGV, used in older contracts and rents. |
| SELIC | `selic_monthly` | The central bank's policy rate, accumulated per month. |
| SGS | `sgs_series` | The central bank's time-series system and public API, the source of every index here. |
| Tabela Prática do TJSP | `index = "tjsp"` | The São Paulo court's official adjustment table: INPC until 07/2024, IPCA-15 from 08/2024 (Law 14,905). Reproducible here from Aug/1995. |
| índices oficiais do TJDFT | `index = "tjdft"` | The Federal District court's composite: INPC until 08/2024, full IPCA from 09/2024. The default outside São Paulo after Law 14,905. |
| Lei 14.905/2024 | Law 14,905/2024 | The 2024 statute that made IPCA the default adjustment index and created the Legal Rate for civil debts. |
| JuriscalcWeb | benchmark | The TJDFT's public calculator, used as the reference for cases 01 to 10. |
| Dr. Calc | benchmark | A commercial court-calculation service, used as the reference for cases 11 to 14 (TJSP table, dated entries, late fine). |

## Deductions and surcharges

| Portuguese | In the code | Meaning |
|---|---|---|
| pena convencional / cláusula penal | `penalty_pct`, `penalty_base` | A contractual penalty DEDUCTED from the refund in a real-estate rescission (e.g. the seller keeps 25 %). |
| deduções (fruição, condominiais, corretagem) | `deductions` | Fixed amounts deducted from the refund: assessed usage fee, condominium charges, brokerage. |
| multa moratória / contratual | `late_fine_pct`, `late_fine` | A fine that ADDS to the debt, computed per installment over the adjusted amount. |
| honorários sucumbenciais (art. 85 CPC) | `awarded_fee_pct`, `awarded_fees` | Attorney fees the court awards to the winning party's lawyer; they belong to the lawyer. |
| honorários como objeto da execução | `awarded_fees_are_the_claim` | The enforcement collects only the awarded fees; the award is just the base of the calculation. |
| honorários do título | `title_fee_pct`, `title_fees` | Fees provided for in the enforced title itself (a clause the debtor consented to); they add to the debt. |
| honorários contratuais | `contract_fee_pct`, `contract_fees` | Fees between the creditor and their own lawyer; informative, never part of the debt. |
| valor da causa | `claim_value` | The stated value of the claim, an alternative base for awarded fees. |
| custas judiciais / despesas processuais | `entries` of kind `court_fee` / `expense` | Court fees and procedural expenses, adjusted from their own date, added without interest. |
| desconto / abatimento | `entries` of kind `discount` | A recognised partial payment or abatement, adjusted from its own date and subtracted. |
| montante exequendo | `enforceable_amount` | The debt being enforced; the base of the art. 523 surcharges. |
| multa e honorários do art. 523, § 1º, CPC | `fine_523_pct`, `fee_523_pct` | The 10 % fine and 10 % fees that accrue when the debtor does not pay within 15 days of the enforcement order. |
| montante do credor | `creditor_amount` | What the creditor actually receives: net amount plus the art. 523 fine; fees go to the lawyer. |
| total do cálculo | `grand_total` | Enforceable amount plus the art. 523 surcharges. |
| cumprimento de sentença | enforcement of a judgment | The procedural phase in which a judgment is enforced. |
| execução de título extrajudicial | enforcement of an extrajudicial title | Enforcement of a contract or debt acknowledgement without a prior judgment. |
| acordo homologado | `settlement` | A settlement approved by the court; it replaces the merits as the base of the calculation. |
| sentença / acórdão / embargos de declaração | judgment / appellate decision / motion for clarification | The kinds of decision the extraction classifies to find the one that governs the calculation. |
