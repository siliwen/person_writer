import { promises as fs } from "fs";
import path from "path";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { parseLegalMarkdown } from "@/lib/legal";
import { LegalDoc } from "@/components/LegalDoc";

const DOC_MAP: Record<string, { file: string; key: string; version: string }> = {
  privacy: { file: "privacy", key: "隐私政策", version: "v1.0" },
  terms: { file: "terms", key: "用户协议", version: "v1.0" },
};

const EFFECTIVE_DATE = "2026年8月16日";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ doc: string }>;
}): Promise<Metadata> {
  const { doc } = await params;
  const meta = DOC_MAP[doc];
  if (!meta) return { title: "协议未找到 · 墨小小" };
  return {
    title: `${meta.key} · 墨小小`,
    description: `墨小小${meta.key}（${meta.version}，生效日期 ${EFFECTIVE_DATE}）`,
  };
}

export default async function LegalPage({
  params,
}: {
  params: Promise<{ doc: string }>;
}) {
  const { doc } = await params;
  const meta = DOC_MAP[doc];
  if (!meta) notFound();

  const filePath = path.join(process.cwd(), "content", "legal", `${meta.file}.md`);
  let raw: string;
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch {
    notFound();
  }

  const parsed = parseLegalMarkdown(raw);

  return (
    <main className="legal-shell">
      <header className="legal-header">
        <div className="legal-header-inner">
          <span className="legal-brand">墨小小</span>
          <span className="legal-header-sep">/</span>
          <span className="legal-header-doc">{meta.key}</span>
          <span className="legal-meta">
            版本 {meta.version} · 生效日期 {EFFECTIVE_DATE}
          </span>
        </div>
      </header>
      <LegalDoc doc={parsed} />
    </main>
  );
}
