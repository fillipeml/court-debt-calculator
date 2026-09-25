import { findColumn, rowsToInstallments, toDecimal, toISO } from "../lib/excel.ts";
import { done, equal, section } from "./harness.mts";

section("toISO: date heuristics of spreadsheet cells");
equal("dd/mm/yyyy", toISO("10/03/2022"), "2022-03-10");
equal("d-m-yyyy", toISO("5-7-2023"), "2023-07-05");
equal("iso passthrough", toISO("2024-06-10"), "2024-06-10");
equal("iso datetime", toISO("2024-06-10T00:00:00"), "2024-06-10");
equal("Date object", toISO(new Date(Date.UTC(2025, 0, 15))), "2025-01-15");
equal("garbage", toISO("next week"), null);
equal("american-looking date is not guessed", toISO("03/10/22"), null);

section("toDecimal: amount heuristics");
equal("brazilian format", toDecimal("R$ 1.850,00"), "1850.00");
equal("plain string", toDecimal("1850"), "1850.00");
equal("number", toDecimal(1850.5), "1850.50");
equal("negative rejected", toDecimal("-10"), null);
equal("zero rejected", toDecimal(0), null);
equal("empty rejected", toDecimal(""), null);

section("findColumn: case-insensitive partial match");
const row = { "Data de Vencimento": "10/03/2022", "Valor Pago": "1.850,00", Histórico: "Parcela 1" };
equal("date column found by 'venc'", findColumn(row, ["venc"]), "10/03/2022");
equal("amount column found by 'pago'", findColumn(row, ["pago"]), "1.850,00");
equal("missing term", findColumn(row, ["zzz"]), null);

section("rowsToInstallments");
equal(
  "portuguese headers",
  rowsToInstallments([row, { "Data de Vencimento": "", "Valor Pago": "", Histórico: "" }]),
  [{ amount: "1850.00", on: "2022-03-10", description: "Parcela 1" }]
);
equal(
  "english headers, receipt date preferred over generic date when listed first",
  rowsToInstallments([{ Date: "01/01/2020", Amount: "100", Note: "x" }]),
  [{ amount: "100.00", on: "2020-01-01", description: "x" }]
);
equal("rows without a date are skipped", rowsToInstallments([{ Amount: "100" }]), []);

done();
