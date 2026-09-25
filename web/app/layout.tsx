import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  applicationName: "Court Debt Calculator",
  title: {
    default: "Court Debt Calculator",
    template: "%s · Court Debt Calculator",
  },
  description:
    "Deterministic update of court-ordered debts in Brazil: monetary adjustment, default interest, " +
    "deductions, fees and enforcement surcharges, with a neutral PDF statement.",
};

export const viewport: Viewport = { themeColor: "#047857" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`h-full antialiased ${inter.variable} ${jetbrains.variable}`}>
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
