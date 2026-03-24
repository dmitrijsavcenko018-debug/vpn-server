import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sector14 VPN",
  description: "Быстрый и понятный VPN сервис"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
