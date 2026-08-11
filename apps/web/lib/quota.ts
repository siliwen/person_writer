import type { ArticleLengthBracket } from "./types";

/** 从「1200字」「12行」等形式中解析出目标字数（整数），与后端 parse_target_length_chars 保持一致。 */
export function parseTargetLengthChars(target: string | null | undefined): number {
  if (!target) return 0;
  const match = target.match(/(\d+)/);
  if (!match) return 0;
  return parseInt(match[1], 10);
}

/** 按长度档位预估文章生成的固定积分，与后端 compute_article_points 保持一致（长文折扣，非严格线性）。 */
export function estimateArticlePoints(chars: number, brackets: ArticleLengthBracket[]): number {
  if (!brackets.length) return 0;
  const sorted = [...brackets].sort((a, b) => a.min_length - b.min_length);
  for (const b of sorted) {
    const upper = b.max_length;
    if (chars >= b.min_length && (upper === null || upper >= chars)) {
      return b.points;
    }
  }
  if (chars < sorted[0].min_length) return sorted[0].points;
  return sorted[sorted.length - 1].points;
}
