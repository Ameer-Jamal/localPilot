"""HTML shell for the transcript view (rendered inside QWebEngineView)."""

HTML_TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/styles/github-dark.min.css">
<script src="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/highlight.min.js"></script>
<style>
  :root { --bg:#0f1115; --panel:#12161a; --text:#e6e6e6; --muted:#9aa5b1; --accent:#4ec9b0; }
  html, body { background: var(--bg); color: var(--text); margin:0; padding:0; }
  body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "JetBrains Mono", monospace; }
  #wrap { padding: 16px 18px; }
  h1,h2,h3{ color: var(--accent); margin: 14px 0 8px; }
  pre { background: #23272e; padding: 12px; border-radius: 8px; overflow:auto; }
  code { background: #23272e; padding: 2px 4px; border-radius: 4px; }
  .role { color: var(--muted); font-size: 12px; margin: 10px 0 4px; }
  hr { border:0; height:1px; background:#2b3137; margin:16px 0; }
</style>
<script>
  function setHtml(html) {
    const c = document.getElementById('wrap');
    c.innerHTML = html;
    try { hljs.highlightAll(); } catch(e) {}
    window.scrollTo(0, document.body.scrollHeight);
  }
</script>
</head><body><div id="wrap"></div></body></html>
"""