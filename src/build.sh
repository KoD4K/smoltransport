#!/bin/sh
# Assemble site/index.html from the parts in src/. The server (smoltransport.ru) takes its code from site/.
# Until github.io is switched to a redirect, the same page is also copied to the repo root for GitHub Pages.
set -e
cd "$(dirname "$0")/.."
{ cat src/head.html; echo '<style>'; cat src/base.css src/extra.css; echo '</style>'; echo '</head>'; echo '<body>'; cat src/body.html; echo '</body>'; echo '</html>'; } > site/index.html
[ -f .pages-redirect ] || cp site/index.html index.html
