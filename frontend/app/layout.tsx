import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TTB AI Alcohol Label Verifier",
  description: "Batch-verify alcohol labels with OCR + Claude extraction + rules.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
