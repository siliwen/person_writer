# -*- coding: utf-8 -*-
import os, re, shutil, json

ROOT = "D:/AI_talk/personal_writing_agent_saas"
EXIST = os.path.join(ROOT, "测评集", "中国近代文学作品集")
LUXUN = "D:/AI_talk/personal_writing_agent_saas/.cache/luxun"
OUT = os.path.join(ROOT, "测评集", "公开文章素材库")
GENRES = ["故事", "小说", "剧本", "诗歌", "杂文", "随笔"]

# 从头清空输出目录，避免历史碎片残留
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)
for g in GENRES:
    os.makedirs(os.path.join(OUT, g), exist_ok=True)

manifest = []

# ---------- 1) 复用现有简体语料（仅公版作者；跳过巴金/茅盾） ----------
REUSE = {
    "鲁迅": {
        "狂人日记.txt": ("小说", "冷峻白描/批判现实"),
        "孔乙己.txt": ("小说", "冷峻白描/讽刺"),
        "药.txt": ("小说", "冷峻/象征"),
        "故乡.txt": ("小说", "抒情白描/苍凉"),
        "社戏.txt": ("小说", "回忆/乡土"),
        "从百草园到三味书屋.txt": ("随笔", "回忆散文/清新"),
        "藤野先生.txt": ("随笔", "纪实散文"),
        "风筝.txt": ("随笔", "抒情/自省"),
        "秋夜.txt": ("诗歌", "散文诗/象征"),
        "纪念刘和珍君.txt": ("杂文", "沉痛杂文/批判"),
    },
    "周作人": "随笔:冲淡闲适/小品文",
    "胡适": {
        "尝试集选.txt": ("诗歌", "早起新诗/白话"),
        "差不多先生传.txt": ("故事", "讽刺寓言/白话"),
        "赠与今年的大学毕业生.txt": ("随笔", "演讲体散文"),
        "追悼志摩.txt": ("随笔", "悼文/平实"),
        "我的母亲.txt": ("随笔", "亲情散文"),
        "多研究些问题少谈些主义.txt": ("杂文", "时事杂文/说理"),
    },
    "徐志摩": {
        "徐志摩诗选.txt": ("诗歌", "唯美抒情诗"),
        "我所知道的康桥.txt": ("随笔", "抒情散文"),
        "翡冷翠山居闲话.txt": ("随笔", "闲适散文"),
        "想飞.txt": ("随笔", "抒情散文"),
        "自剖.txt": ("随笔", "自省散文"),
        "北戴河海滨的幻想.txt": ("随笔", "写景散文"),
    },
    "朱自清": "随笔:抒情散文/细腻",
    "老舍": {
        "济南的冬天.txt": ("随笔", "京味散文/温润"),
        "想北平.txt": ("随笔", "乡愁散文"),
        "我的母亲.txt": ("随笔", "亲情散文"),
        "月牙儿.txt": ("小说", "京味/悲情写实"),
        "微神.txt": ("小说", "京味/抒情小说"),
        "猫.txt": ("随笔", "闲适散文"),
        "养花.txt": ("随笔", "生活散文"),
        "北京的春节.txt": ("随笔", "民俗散文"),
        "趵突泉.txt": ("随笔", "写景散文"),
        "宗月大师.txt": ("随笔", "记人散文"),
    },
}

def add_manifest(genre, fname, title, author, source, copyright, style):
    manifest.append({"genre": genre, "file": fname, "title": title, "author": author,
                     "source": source, "copyright": copyright, "style_tags": style})

SKIP_TITLES = {"自序", "序言", "小引", "题记", "题辞", "后记", "附录", "目录", "索引", "例言", "弁言"}

def clean_title(t):
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[\^[^\]]*\]", "", t)
    t = re.sub(r"[〔\[].*?[〕\]]", "", t)
    t = t.replace("*", "").strip()
    t = re.sub(r"\s+", " ", t)
    return t

for author, spec in REUSE.items():
    adir = os.path.join(EXIST, author)
    if not os.path.isdir(adir):
        continue
    for fn in os.listdir(adir):
        if not fn.endswith(".txt"):
            continue
        src = os.path.join(adir, fn)
        if isinstance(spec, str):
            genre, style = tuple(spec.split(":", 1))
        else:
            if fn not in spec:
                continue
            genre, style = spec[fn]
        title = fn[:-4]
        newname = f"{author}_{title}.txt"
        dst = os.path.join(OUT, genre, newname)
        shutil.copy2(src, dst)
        add_manifest(genre, newname, title, author, "中国近代文学作品集(维基文库简体整理)", "公版", style)
print("REUSE done:", len(manifest))

# ---------- 2) 收割 luxun 仓库 ----------
LUXUN_BOOKS = {
    "呐喊": ("鲁迅", "公版(逝1936)"), "彷徨": ("鲁迅", "公版(逝1936)"),
    "故事新编": ("鲁迅", "公版(逝1936)"), "野草": ("鲁迅", "公版(逝1936)"),
    "朝花夕拾": ("鲁迅", "公版(逝1936)"),
    "华盖集": ("鲁迅", "公版(逝1936)"), "华盖集续编": ("鲁迅", "公版(逝1936)"),
    "华盖集续编的续编": ("鲁迅", "公版(逝1936)"), "坟": ("鲁迅", "公版(逝1936)"),
    "热风": ("鲁迅", "公版(逝1936)"), "且介亭杂文": ("鲁迅", "公版(逝1936)"),
    "且介亭杂文二编": ("鲁迅", "公版(逝1936)"), "且介亭杂文续编": ("鲁迅", "公版(逝1936)"),
    "而已集": ("鲁迅", "公版(逝1936)"), "二心集": ("鲁迅", "公版(逝1936)"),
    "南腔北调集": ("鲁迅", "公版(逝1936)"), "伪自由书": ("鲁迅", "公版(逝1936)"),
    "准风月谈": ("鲁迅", "公版(逝1936)"), "花边文学": ("鲁迅", "公版(逝1936)"),
}
BOOK_GENRE = {
    "呐喊": "故事", "彷徨": "故事", "故事新编": "小说", "野草": "诗歌",
    "朝花夕拾": "随笔",
    "华盖集": "杂文", "华盖集续编": "杂文", "华盖集续编的续编": "杂文", "坟": "杂文",
    "热风": "杂文", "且介亭杂文": "杂文", "且介亭杂文二编": "杂文",
    "且介亭杂文续编": "杂文", "而已集": "杂文", "二心集": "杂文",
    "南腔北调集": "杂文", "伪自由书": "杂文", "准风月谈": "杂文", "花边文学": "杂文",
}
SPECIAL = {"阿Q正传": "小说"}  # 在呐喊里，归入小说
STYLE = {
    "野草": "散文诗/象征凝练", "朝花夕拾": "回忆散文/温润",
    "呐喊": "冷峻白描/批判", "彷徨": "忧愤深广/写实", "故事新编": "历史小说/讽刺",
}

for book, (author, copyright) in LUXUN_BOOKS.items():
    path = os.path.join(LUXUN, book + ".md")
    if not os.path.isfile(path):
        print("MISSING", book); continue
    text = open(path, encoding="utf-8").read()
    genre = BOOK_GENRE[book]
    source = "维基文库/aronstonehiggs-luxun"
    if genre == "杂文":
        body = text.strip()
        newname = f"{author}_{book}.txt"
        dst = os.path.join(OUT, genre, newname)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        add_manifest(genre, newname, book, author, source, copyright, "杂文/投枪匕首")
        print(f"LUXUN {book}: 整本({len(body)}字)")
        continue
    pat = re.compile(r"^#{1,4}\s+(.+?)\s*$", re.M)
    matches = list(pat.finditer(text))
    style = STYLE.get(book, "鲁迅体/冷峻犀利")
    n = 0
    for i, m in enumerate(matches):
        if i == 0:
            continue  # 书标题
        title = clean_title(m.group(1))
        if title in SKIP_TITLES or not title:
            continue
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        body = text[start:end].strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if len(body) < 30:
            continue
        g = SPECIAL.get(title, genre)
        newname = f"{author}_{title}.txt"
        dst = os.path.join(OUT, g, newname)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        add_manifest(g, newname, title, author, source, copyright, style)
        n += 1
    print(f"LUXUN {book}: 拆分 {n} 篇")

with open(os.path.join(OUT, "corpus_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print("\n=== 各体裁文件数 ===")
for g in GENRES:
    files = [x for x in os.listdir(os.path.join(OUT, g)) if x.endswith(".txt")]
    print(f"{g}: {len(files)}")
print("TOTAL manifest:", len(manifest))
