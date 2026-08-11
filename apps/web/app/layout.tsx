import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "墨小小 - 个人风格写作",
  description: "上传你的作品，提取独属于你的写作风格，让 AI 按你的风格生成文章、散文、小说和诗歌。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 在首屏绘制前应用主题，避免闪烁（FOUC） */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('moxx-theme');if(t!=='violet'&&t!=='ink'&&t!=='swiss'){t='ink';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','ink');}})();",
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
