# -*- coding: utf-8 -*-
import os, re, json, zhconv, shutil

ROOT = "D:/AI_talk/personal_writing_agent_saas"
OUT = os.path.join(ROOT, "测评集", "公开文章素材库")
GENRES = ["故事", "小说", "剧本", "诗歌", "杂文", "随笔"]

AUTHOR_STYLE = {
    "关汉卿": "元杂剧/本色泼辣", "王实甫": "元杂剧/华美", "马致远": "元杂剧/苍凉",
    "白朴": "元杂剧/婉约", "纪君祥": "元杂剧/悲壮", "汤显祖": "明传奇/绮丽",
    "洪昇": "清传奇/抒情", "孔尚任": "清传奇/兴亡之感", "郑光祖": "元杂剧/情致",
    "老舍": "京味话剧/平民", "田汉": "现代话剧/浪漫", "欧阳予倩": "现代话剧/写实",
    "戴望舒": "现代诗/象征", "闻一多": "现代诗/格律", "胡适": "现代诗/白话",
    "刘半农": "现代诗/民歌风", "李白": "唐诗/豪放", "杜甫": "唐诗/沉郁",
    "苏轼": "宋词/旷达", "李清照": "宋词/婉约", "王维": "唐诗/恬淡",
    "梁启超": "近代政论/雄辩", "陈独秀": "近代杂文/启蒙", "李大钊": "近代杂文/激越",
}

PREAMBLE = [
    "维基文库", "自由的图书馆", "跳转到内容", "本作品收录于", "姊妹计划", "数据项",
    "版本信息", "TextInfo", "upload.wikimedia.org", "zh.wikisource.org", "zh.wikipedia.org",
    "zh.wikibooks.org", "zh.wikiquote.org", "Wikimedia-logo", "Information_icon", "参阅",
    "维基百科", "修订间差异", "此页面目前没有内容", "创建此页面", "搜索此页面",
    "重定向自", "本页面最后", "分类：", "标签：", "公众领域", "Public Domain",
    "本作品在", "根据", "授权", "原载", "初载", "署名", "作者：", "收录于",
]

def clean_text(text):
    lines = text.split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        # 丢弃导航/元数据行
        low = s.lower()
        if any(p.lower() in low for p in PREAMBLE):
            continue
        # 丢弃 markdown 链接行 / 图片行
        if re.match(r"^!?\[.*\]\(.*\)$", s):
            continue
        # 丢弃 [[编辑]] 章节标记行（wikisource 导航残留）
        if "[[编辑" in s or "编辑章节" in s:
            continue
        # 丢弃整行加粗的标题/作者重复行（如 **篇名**）
        if re.match(r"^\*\*[^*\n]+\*\*\s*$", s):
            continue
        # 丢弃 **标题**: ... 行
        if s.startswith("**标题**"):
            continue
        # 丢弃纯 URL 行
        if s.startswith("http://") or s.startswith("https://"):
            continue
        out.append(ln)
    body = "\n".join(out).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    # 去掉开头的 H1 标题行（书/篇名）
    body = re.sub(r"^\s*#\s+.+\n", "", body, count=1)
    # 繁 -> 简
    body = zhconv.convert(body, "zh-cn")
    return body.strip() + "\n"

# 1) 清洗 wf_ 前缀的原始抓取文件
TRASH = os.path.join(OUT, ".corpus_trash")
os.makedirs(TRASH, exist_ok=True)
for g in GENRES:
    gd = os.path.join(OUT, g)
    if not os.path.isdir(gd):
        continue
    for fn in os.listdir(gd):
        if not fn.startswith("wf_") or not fn.endswith(".txt"):
            continue
        src = os.path.join(gd, fn)
        raw = open(src, encoding="utf-8").read()
        cleaned = clean_text(raw)
        final_name = fn[3:]  # 去掉 wf_
        dst = os.path.join(gd, final_name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(cleaned)
        shutil.move(src, os.path.join(TRASH, fn))
        print(f"cleaned {g}/{final_name} ({len(cleaned)}字)")

# 2) 重新生成 manifest + 每类索引
manifest = []
for g in GENRES:
    gd = os.path.join(OUT, g)
    files = sorted([x for x in os.listdir(gd) if x.endswith(".txt")])
    for fn in files:
        title = fn[:-4]
        author = ""
        if "_" in title:
            maybe = title.split("_", 1)[0]
            if maybe in AUTHOR_STYLE or maybe in ("鲁迅","周作人","胡适","徐志摩","朱自清","老舍","郁达夫","许地山","废名","萧红","王统照","柔石","庐隐","沈复","夏丏尊","梁启超","陈独秀","李大钊","瞿秋白"):
                author = maybe
                title = title.split("_", 1)[1]
        style = AUTHOR_STYLE.get(author, "")
        manifest.append({"genre": g, "file": fn, "title": title, "author": author,
                         "style_tags": style})
    # 索引.md
    with open(os.path.join(gd, "索引.md"), "w", encoding="utf-8") as f:
        f.write(f"# {g}（共 {len(files)} 篇）\n\n")
        f.write("| # | 文件 | 篇名 | 作者 | 风格标签 | 来源 |\n")
        f.write("|---|------|------|------|----------|------|\n")
        for i, fn in enumerate(files, 1):
            t = fn[:-4]
            a = ""
            if "_" in t:
                m = t.split("_", 1)[0]
                if m in AUTHOR_STYLE or m in ("鲁迅","周作人","胡适","徐志摩","朱自清","老舍"):
                    a = m; t = t.split("_", 1)[1]
            st = AUTHOR_STYLE.get(a, "")
            src = "维基文库/克隆仓库" if a in ("鲁迅",) else "维基文库"
            f.write(f"| {i} | {fn} | {t} | {a} | {st} | {src} |\n")

with open(os.path.join(OUT, "corpus_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

# 3) 总 README
with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
    f.write("# 公开文章素材库（六类型 · 公版中文）\n\n")
    f.write("> 用途：为「墨写」故事风格写作测试提供公开、合规（公版）的中文文章素材。\n")
    f.write("> 来源：维基文库（zh.wikisource.org）、GitHub 克隆仓库 aronstonehiggs/luxun（鲁迅全集）、项目既有《中国近代文学作品集》（简体整理）。\n")
    f.write("> 版权：全部为公版（作者逝世满 50 年）或古典作品；已剔除版权未到期作者（巴金、茅盾等）。\n\n")
    f.write("## 各类型篇数\n\n")
    f.write("| 类型 | 篇数 |\n|---|---|\n")
    for g in GENRES:
        n = len([x for x in os.listdir(os.path.join(OUT, g)) if x.endswith(".txt")])
        f.write(f"| {g} | {n} |\n")
    f.write("\n## 说明\n- 诗歌含散文诗（鲁迅《野草》）；小说含中短篇与历史小说；杂文为鲁迅各杂文集整本 + 近代政论。\n")
    f.write("- 文本均为简体中文；克隆/现有文件本就简体，维基文库抓取件已用 OpenCC(zhconv) 繁转简。\n")
    f.write("- 每类目录下含 `索引.md` 列出篇目与作者；根目录 `corpus_manifest.json` 为机器可读清单。\n")

print("\n=== 最终各体裁文件数 ===")
for g in GENRES:
    n = len([x for x in os.listdir(os.path.join(OUT, g)) if x.endswith(".txt")])
    print(f"{g}: {n}")
