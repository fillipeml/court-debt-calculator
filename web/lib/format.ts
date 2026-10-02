/** Formatting helpers. Amounts are Brazilian reais and keep the Brazilian format
 *  (R$ 1.234,56): the statement goes into a Brazilian court file. Dates are dd/mm/yyyy. */

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** "162363.32" -> "R$ 162.363,32" (string arithmetic, no float rounding of the cents). */
export const brl = (value: string | number): string => {
  const text = typeof value === "number" ? value.toFixed(2) : String(value);
  const negative = text.startsWith("-");
  const [integer, decimals = "00"] = text.replace("-", "").split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${negative ? "-" : ""}R$ ${grouped},${(decimals + "00").slice(0, 2)}`;
};

/** "2026-05-22" -> "22/05/2026". */
export const dateBR = (iso: string): string => {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

/** "2026-05" -> "May 2026". */
export const monthLabel = (month: string): string => {
  if (!/^\d{4}-\d{2}$/.test(month)) return month;
  return `${MONTHS[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}`;
};

/** Formats an amount while the user types: thousands separators in the integer part
 *  (10000 -> 10.000), keeps the decimal comma and limits it to 2 places. */
export const formatAmountBR = (text: string): string => {
  const clean = text.replace(/[^\d,]/g, "");
  if (clean === "") return "";
  const comma = clean.indexOf(",");
  const rawInteger = (comma >= 0 ? clean.slice(0, comma) : clean).replace(/^0+(?=\d)/, "");
  const grouped = (rawInteger || "0").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  if (comma < 0) return grouped;
  const dec = clean.slice(comma + 1).replace(/,/g, "").slice(0, 2);
  return `${grouped},${dec}`;
};

/** "1.850,00" -> "1850.00"; returns null when empty or not a positive number. */
export const parseAmountBR = (text: string): string | null => {
  const value = text.replace(/\./g, "").replace(",", ".").trim();
  if (!value || isNaN(Number(value)) || Number(value) <= 0) return null;
  return value;
};

/** Percentage input: accepts "1,5" and "1.5". */
export const parsePct = (text: string): string => text.replace(",", ".").trim();

export const today = (): string => new Date().toISOString().slice(0, 10);

export const previousMonth = (): string => {
  const d = new Date();
  // Step the day to the 1st first: setMonth keeps the day number, so on the 31st of a month
  // whose predecessor is shorter it overflows forward and lands back in the current month.
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};
