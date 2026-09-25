import { creditorAmountNote, readableDetail, type Totals } from "../lib/api.ts";
import { check, done, equal, section } from "./harness.mts";

const totals = (over: Partial<Totals>): Totals => ({
  original: "0.00",
  adjusted: "0.00",
  interest: "0.00",
  late_fine: "0.00",
  gross_total_A: "0.00",
  penalty: "0.00",
  fixed_deductions: "0.00",
  total_deductions: "0.00",
  net_amount: "0.00",
  awarded_fees: "0.00",
  awarded_fee_base: "0.00",
  title_fees: "0.00",
  title_fee_base: "0.00",
  adjusted_claim_value: null,
  fees_and_expenses: "0.00",
  discounts: "0.00",
  enforceable_amount: "0.00",
  fine_523_B: "0.00",
  fee_523_C: "0.00",
  creditor_amount: "0.00",
  contract_fees: null,
  creditor_after_contract_fees: null,
  grand_total: "0.00",
  ...over,
});

section("creditorAmountNote");
equal("nothing to explain", creditorAmountNote(totals({}), {}), null);
check(
  "awarded fees and the art. 523 fine",
  creditorAmountNote(totals({ awarded_fees: "10.00", fine_523_B: "5.00" }), {})?.startsWith(
    "= enforceable amount − awarded fees + art. 523 fine"
  ) === true
);
check(
  "title fees only",
  creditorAmountNote(totals({ title_fees: "10.00" }), {}) === "= enforceable amount − title fees (they belong to the lawyer, CPC art. 85 §14)"
);
check(
  "awarded and title fees together",
  creditorAmountNote(totals({ awarded_fees: "1.00", title_fees: "1.00" }), {})?.includes("awarded and title fees") === true
);
check(
  "fees as the claim are not subtracted",
  creditorAmountNote(totals({ awarded_fees: "10.00", fine_523_B: "1.00" }), { awarded_fees_are_the_claim: true }) ===
    "= enforceable amount + art. 523 fine (the fine belongs to the creditor)"
);

section("readableDetail: FastAPI validation errors");
equal("string passthrough", readableDetail("Index unavailable"), "Index unavailable");
equal(
  "pydantic error names the field",
  readableDetail([{ loc: ["body", "installments", 0, "amount"], msg: "Value error, installment amount must be greater than zero" }]),
  "Field “installments → 0 → amount”: installment amount must be greater than zero"
);
equal("empty list", readableDetail([]), null);
equal("unknown shape", readableDetail({ weird: true }), null);

done();
