const form = document.querySelector("#extract-form");
const urlInput = document.querySelector("#url-input");
const extractButton = document.querySelector("#extract-button");
const statusBox = document.querySelector("#status");
const resultSection = document.querySelector("#result-section");
const downloadButton = document.querySelector("#download-button");

let currentArticle = null;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.hidden = !message;
  statusBox.classList.toggle("error", isError);
}

function setLoading(loading) {
  extractButton.disabled = loading;
  extractButton.querySelector("span").textContent = loading ? "正在提取…" : "提取正文";
}

function renderArticle(article) {
  document.querySelector("#site-name").textContent = article.site_name || "网页作品";
  document.querySelector("#char-count").textContent = `${article.char_count.toLocaleString("zh-CN")} 字符`;
  document.querySelector("#article-title").textContent = article.title;
  const byline = [article.author, article.published_at].filter(Boolean).join("  ·  ");
  document.querySelector("#article-byline").textContent = byline;

  const content = document.querySelector("#article-content");
  content.replaceChildren();
  article.blocks.forEach((block) => {
    const element = document.createElement(block.type === "heading" ? "h4" : "p");
    element.textContent = block.text;
    content.appendChild(element);
  });

  const sourceLink = document.querySelector("#source-link");
  sourceLink.href = article.source_url;
  sourceLink.textContent = `原始网址：${article.source_url}`;
  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  setStatus("正在读取网页并识别正文，请稍候…");
  resultSection.hidden = true;
  currentArticle = null;

  try {
    const response = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value.trim() }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "正文提取失败。");
    currentArticle = data.article;
    renderArticle(currentArticle);
    setStatus(`提取完成，共识别 ${currentArticle.blocks.length} 个正文段落。`);
  } catch (error) {
    setStatus(error.message || "正文提取失败。", true);
  } finally {
    setLoading(false);
  }
});

downloadButton.addEventListener("click", async () => {
  if (!currentArticle) return;
  downloadButton.disabled = true;
  try {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentArticle),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Word 文档生成失败。");
    }
    setStatus(`Word 文档已保存到项目 ${data.saved_directory}/${data.saved_filename}。`);
  } catch (error) {
    setStatus(error.message || "Word 文档生成失败。", true);
  } finally {
    downloadButton.disabled = false;
  }
});
