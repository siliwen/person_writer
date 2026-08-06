import io
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import (
    filename_for_article,
    parse_article,
    save_article_docx,
)


FIXTURE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <title>导航标题</title>
  <meta property="og:title" content="雨夜里的旧书店">
  <meta name="author" content="测试作者">
  <meta property="article:published_time" content="2026-08-04">
  <meta property="og:site_name" content="示例文学网">
</head>
<body>
  <nav>首页 推荐 热榜</nav>
  <main>
    <article class="article-content">
      <h1>雨夜里的旧书店</h1>
      <p>雨从傍晚开始下，沿着窄巷里的青石一级一级漫过来。书店的木门没有关严，灯光落在门槛上。</p>
      <h2>迟到的来客</h2>
      <p>他收起伞，先看见靠墙那排旧书，再看见柜台后安静翻页的人。空气里有纸张和潮木头的气味。</p>
      <p>没有人催促他开口。雨声替两个人填满了沉默，像一段已经写好、却还没有署名的序言。</p>
    </article>
  </main>
  <aside>猜你喜欢：十篇热门文章</aside>
</body>
</html>
"""

CHINA_WRITER_FIXTURE = """
<!doctype html>
<html><head>
  <title>莫言：小时候的年--专题--中国作家网</title>
  <meta name="publishdate" content="2026-02-27">
  <meta name="author" content="104645">
</head><body>
  <h1 class="logo">中国作家协会主管</h1>
  <main><div class="list_warp clearfix">
    <h6 class="end_tit"><em id="newstit">莫言：小时候的年</em></h6>
    <div class="end_info clearfix">来源：《印象春节》 | 莫言 <em>2026年02月27日16:01</em></div>
    <div class="end_article">
      <p>小时盼年，其实与食物有关。那时候农村最好的食物就是饺子，再就是年糕，这些食物，只有在过年时才可以吃到。</p>
      <p>春节期间吃的是素馅饺子，豆腐粉条菠菜白菜。为什么要吃素馅饺子呢？老人说是因为神不能吃荤。</p>
    </div>
  </div></main>
</body></html>
"""


class ArticleCollectorTests(unittest.TestCase):
    def test_extracts_article_and_ignores_navigation(self):
        article = parse_article(FIXTURE, "https://example.com/story")
        self.assertEqual(article.title, "雨夜里的旧书店")
        self.assertEqual(article.author, "测试作者")
        self.assertEqual(article.site_name, "示例文学网")
        self.assertNotIn("猜你喜欢", article.text)
        self.assertNotIn("首页", article.text)
        self.assertGreaterEqual(len(article.blocks), 4)

    def test_generates_valid_docx_with_source_and_body(self):
        article = parse_article(FIXTURE, "https://example.com/story")
        with TemporaryDirectory() as directory:
            _, payload = save_article_docx(article, Path(directory))
        self.assertGreater(len(payload), 10000)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("雨夜里的旧书店", document_xml)
            self.assertIn("迟到的来客", document_xml)
            self.assertIn("Microsoft YaHei", document_xml)

    def test_china_writer_title_author_filename_and_save_path(self):
        article = parse_article(
            CHINA_WRITER_FIXTURE,
            "https://www.chinawriter.com.cn/n1/2026/0227/example.html",
        )
        self.assertEqual(article.title, "莫言：小时候的年")
        self.assertEqual(article.author, "莫言")
        self.assertEqual(article.published_at, "2026-02-27")
        self.assertEqual(filename_for_article(article), "莫言+小时候的年.docx")
        with TemporaryDirectory() as directory:
            output_path, payload = save_article_docx(article, Path(directory))
            self.assertEqual(output_path.name, "莫言+小时候的年.docx")
            self.assertEqual(output_path.read_bytes(), payload)

if __name__ == "__main__":
    unittest.main()
