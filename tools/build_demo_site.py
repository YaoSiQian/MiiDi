"""构建静态 demo 站点到 docs/demo/，GitHub Pages 开箱即用。

步骤：
1. 在 web/ 下以相对 base 构建前端（vite build --base=./）
2. 清空并拷贝 dist → docs/demo/
3. 注入 demo-data.js / demo-mode.js（真实主站构建不含这两个文件）
4. 拷贝罐头数据与预渲染 MIDI

用法：py tools/build_demo_site.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "web"
DIST = WEB / "dist"
OUT = REPO_ROOT / "docs" / "demo"


def main() -> None:
    subprocess.run(["npm", "run", "build", "--", "--base=./"], cwd=WEB, check=True, shell=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(DIST, OUT)

    for name in ("demo-mode.js", "demo-data.js", "demo.mid"):
        src = WEB / "demo" / name if name != "demo-mode.js" else WEB / "js" / name
        shutil.copy2(src, OUT / name)

    index = OUT / "index.html"
    html = index.read_text()
    inject = '<script src="./demo-data.js"></script>\n  <script src="./demo-mode.js"></script>\n  '
    html, n = re.subn(r"(\s*)(<script type=\"module\")", inject + r"\2", html, count=1)
    if n != 1:
        raise SystemExit("module script tag not found in built index.html")
    index.write_text(html)
    print(f"demo site ready: {OUT}")


if __name__ == "__main__":
    main()
