import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sector14 VPN",
  description: "VPN SaaS mock product"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
