#!/usr/bin/env python3
"""Build standalone HTML from the HAS Markdown sources.

Usage: python build.py
Outputs into ./build/ (git-ignored).
"""
from __future__ import annotations

import pathlib

import markdown

ROOT = pathlib.Path(__file__).parent
DOCS = ROOT / "docs"
OUT = ROOT / "build"

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1b1f23}
h1,h2,h3{line-height:1.25;margin-top:1.6em}
h1{border-bottom:2px solid #d0d7de;padding-bottom:.3em}
h2{border-bottom:1px solid #d0d7de;padding-bottom:.2em}
code{background:#f6f8fa;padding:.15em .3em;border-radius:4px;font-size:90%}
pre{background:#f6f8fa;padding:1em;border-radius:6px;overflow:auto}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:1em 0}
th,td{border:1px solid #d0d7de;padding:.4em .6em;text-align:left;vertical-align:top}
th{background:#f6f8fa}
blockquote{color:#57606a;border-left:.25em solid #d0d7de;padding:0 1em;margin:0}
"""

EXTS = ["tables", "fenced_code", "toc", "sane_lists"]


def render(md_path: pathlib.Path, out_path: pathlib.Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(text, extensions=EXTS)
    title = md_path.stem
    html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{CSS}</style></head><body>"
        f"{html_body}</body></html>"
    )
    out_path.write_text(html, encoding="utf-8")
    print(f"  {md_path.relative_to(ROOT)} -> {out_path.relative_to(ROOT)}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    print("Building HTML:")
    for md_path in sorted(DOCS.glob("*.md")):
        render(md_path, OUT / (md_path.stem + ".html"))
    print(f"Done. Output in {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
