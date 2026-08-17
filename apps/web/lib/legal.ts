/**
 * 法律协议 Markdown 解析器（聚焦子集）。
 *
 * 支持语法（与 10_legal_法律协议/ 下两份文档一致）：
 * - 标题：# / ## / ###
 * - 无序列表：- 或 * 开头
 * - 有序列表：行首数字编号（含 1. / 1.1 / 11.3 等条款式编号）
 * - 段落：其余非空行
 * - 行内：**加粗**
 *
 * 不引入任何第三方 markdown 依赖，保持前端包体精简。
 */

export type LegalBlock =
  | { type: "heading"; level: 1 | 2 | 3; text: string; id: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] };

export interface LegalTocItem {
  id: string;
  text: string;
  level: 2 | 3;
}

export interface LegalDoc {
  title: string;
  blocks: LegalBlock[];
  toc: LegalTocItem[];
}

const HEADING_RE = /^(#{1,3})\s+(.*)$/;
const UNORDERED_RE = /^[-*]\s+(.*)$/;
const ORDERED_RE = /^\d+(?:\.\d+)*\.?\s+(.*)$/;

export function parseLegalMarkdown(md: string): LegalDoc {
  const lines = md.split(/\r?\n/);
  const blocks: LegalBlock[] = [];
  const toc: LegalTocItem[] = [];
  let headingIndex = 0;

  let listBuffer: { ordered: boolean; items: string[] } | null = null;

  const flushList = () => {
    if (listBuffer && listBuffer.items.length > 0) {
      blocks.push({ type: "list", ordered: listBuffer.ordered, items: listBuffer.items });
    }
    listBuffer = null;
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (line.trim() === "") {
      flushList();
      continue;
    }

    const headingMatch = HEADING_RE.exec(line);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length as 1 | 2 | 3;
      const text = headingMatch[2].trim();
      const id = `sec-${headingIndex++}`;
      blocks.push({ type: "heading", level, text, id });
      if (level === 2 || level === 3) {
        toc.push({ id, text, level });
      }
      continue;
    }

    const unorderedMatch = UNORDERED_RE.exec(line);
    if (unorderedMatch) {
      if (!listBuffer || listBuffer.ordered) {
        flushList();
        listBuffer = { ordered: false, items: [] };
      }
      listBuffer.items.push(unorderedMatch[1].trim());
      continue;
    }

    const orderedMatch = ORDERED_RE.exec(line);
    if (orderedMatch) {
      if (!listBuffer || !listBuffer.ordered) {
        flushList();
        listBuffer = { ordered: true, items: [] };
      }
      listBuffer.items.push(orderedMatch[1].trim());
      continue;
    }

    // 普通段落
    flushList();
    blocks.push({ type: "paragraph", text: line.trim() });
  }
  flushList();

  const title = blocks.find((b) => b.type === "heading" && b.level === 1);
  return {
    title: title && title.type === "heading" ? title.text : "协议",
    blocks,
    toc,
  };
}
