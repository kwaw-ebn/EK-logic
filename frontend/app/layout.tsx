import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "EK-Logic | Turn Data Into Decisions",
  description: "Your workspace for business and marketing intelligence.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
