import type { ReactNode } from "react";
import type { LegalBlock, LegalDoc } from "@/lib/legal";

/**
 * 渲染行内 **加粗**。无第三方依赖，仅处理 **...** 这一种标记。
 */
function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const bold = /^\*\*([^*]+)\*\*$/.exec(part);
    if (bold) return <strong key={i}>{bold[1]}</strong>;
    return <span key={i}>{part}</span>;
  });
}

export function LegalDoc({ doc }: { doc: LegalDoc }) {
  return (
    <div className="legal-page" id="top">
      <div className="legal-layout">
        <nav className="legal-toc" aria-label="目录">
          <div className="legal-toc-title">目录</div>
          <ul>
            {doc.toc.map((t) => (
              <li key={t.id} className={t.level === 3 ? "legal-toc-sub" : undefined}>
                <a href={`#${t.id}`}>{t.text}</a>
              </li>
            ))}
          </ul>
        </nav>

        <article className="legal-content">
          {doc.blocks.map((b, i) => {
            if (b.type === "heading") {
              const Tag = (["h1", "h2", "h3"] as const)[b.level - 1];
              return (
                <Tag key={i} id={b.id} className={`legal-h${b.level}`}>
                  {b.text}
                </Tag>
              );
            }
            if (b.type === "paragraph") {
              return (
                <p key={i} className="legal-p">
                  {renderInline(b.text)}
                </p>
              );
            }
            if (b.type === "list") {
              const ListTag = b.ordered ? "ol" : "ul";
              return (
                <ListTag
                  key={i}
                  className={`legal-list ${b.ordered ? "legal-list-ordered" : "legal-list-unordered"}`}
                >
                  {b.items.map((it, j) => (
                    <li key={j}>{renderInline(it)}</li>
                  ))}
                </ListTag>
              );
            }
            return null;
          })}
          <a href="#top" className="legal-backtop">
            回到顶部 ↑
          </a>
        </article>
      </div>
    </div>
  );
}
