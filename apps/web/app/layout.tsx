import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "墨写 - 个人风格写作",
  description: "上传你的作品，提取独属于你的写作风格，让 AI 按你的风格生成文章、散文、小说和诗歌。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
