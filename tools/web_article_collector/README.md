# 网页作品采集器

用于初试测评集素材整理的本地网页工具。输入公开网页地址后，工具会提取标题、作者、发布日期、小标题和正文，并导出为 Word 可打开的 `.docx` 文件。

点击“保存 Word”后，服务端会直接把文件保存到项目的 `测评集/网页作品` 目录，不调用浏览器下载。文件名采用 `作者+文章名字.docx`，例如 `莫言+小时候的年.docx`。

## 启动

在 PowerShell 中运行：

```powershell
cd D:\AI_talk\personal_writing_agent_saas\tools\web_article_collector
.\start.ps1
```

浏览器打开 `http://127.0.0.1:8765`。

如果提示缺少依赖，先运行：

```powershell
.\setup.ps1
```

## 当前边界

- 仅支持公开的 HTTP/HTTPS HTML 网页。
- 不绕过登录、付费墙、验证码、访问控制或反爬机制。
- 对完全依赖 JavaScript 动态加载正文的网页，可能无法提取。
- 出于安全考虑，不允许抓取本机、局域网或其他私有网络地址。
- 单个网页响应上限为 5 MB，抓取超时为 15 秒。

## 导出产物

每次导出只生成 `作者+文章名字.docx`，用于人工审阅和内部测评。

## 测试

```powershell
$py = "C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py -m unittest discover -s tests -v
```
