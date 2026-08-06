import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Personal Writing Agent",
  description: "Style Profile first personal writing SaaS MVP"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

