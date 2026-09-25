import { brl, dateBR, formatAmountBR, monthLabel, parseAmountBR, parsePct } from "../lib/format.ts";
import { done, equal, section } from "./harness.mts";

section("brl: Brazilian currency formatting from decimal strings");
equal("cents preserved", brl("162363.32"), "R$ 162.363,32");
equal("thousands grouping", brl("1000000.00"), "R$ 1.000.000,00");
equal("small amount", brl("72.67"), "R$ 72,67");
equal("integer string gets cents", brl("5"), "R$ 5,00");
equal("one decimal padded", brl("5.5"), "R$ 5,50");
equal("negative", brl("-309.07"), "-R$ 309,07");
equal("number input", brl(1234.5), "R$ 1.234,50");

section("dateBR / monthLabel");
equal("iso to dd/mm/yyyy", dateBR("2026-05-22"), "22/05/2026");
equal("month label", monthLabel("2026-04"), "April 2026");
equal("month label passthrough", monthLabel("garbage"), "garbage");

section("formatAmountBR: typing mask");
equal("groups thousands", formatAmountBR("10000"), "10.000");
equal("keeps decimal comma", formatAmountBR("1850,5"), "1.850,5");
equal("limits to two decimals", formatAmountBR("1850,123"), "1.850,12");
equal("strips letters", formatAmountBR("R$ 1.850,00"), "1.850,00");
equal("empty stays empty", formatAmountBR(""), "");
equal("leading zeros dropped", formatAmountBR("007"), "7");

section("parseAmountBR: mask to decimal string");
equal("br format", parseAmountBR("1.850,00"), "1850.00");
equal("plain integer", parseAmountBR("134000"), "134000");
equal("zero rejected", parseAmountBR("0,00"), null);
equal("empty rejected", parseAmountBR(""), null);
equal("letters rejected", parseAmountBR("abc"), null);

section("parsePct");
equal("comma to dot", parsePct("1,5"), "1.5");
equal("trimmed", parsePct(" 10 "), "10");

done();
