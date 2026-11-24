#!/usr/bin/env python3
"""Build a private-preview copy of public/ for a claude.ai artifact.

  python3 make_preview.py OUT_DIR

The artifact viewer serves files relative to the page, so links like /about
become about.html and /img/... become img/.... index.html loses its
<html>/<head>/<body> wrapper (the viewer adds its own). Prints the list of
supporting files to publish next to index.html.
"""
import json, os, re, shutil, sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
out = sys.argv[1]
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(SRC, out)
os.remove(os.path.join(out, "404.html"))
pages = [f[:-5] for f in os.listdir(out) if f.endswith(".html") and f != "index.html"]
for f in ["index.html"] + [p + ".html" for p in pages]:
    path = os.path.join(out, f)
    s = open(path).read()
    s = s.replace('href="/"', 'href="./"')
    for p in pages:
        s = s.replace(f'href="/{p}"', f'href="{p}.html"')
    s = re.sub(r'(src|href)="/(?!/)', r'\1="', s)
    if f == "index.html":
        s = re.sub(r"(?s)<!doctype html>\s*<html[^>]*>\s*<head>\s*", "", s)
        s = re.sub(r"</head>\s*<body>", "", s)
        s = re.sub(r"</body>\s*</html>\s*$", "", s)
        s = s.replace("<title>Fede Nigro</title>", "<title>Fede Nigro Portfolio</title>")
    open(path, "w").write(s)
files = sorted(os.path.relpath(os.path.join(r, n), out).replace(os.sep, "/")
               for r, _, ns in os.walk(out) for n in ns)
print(json.dumps([{"path": p} for p in files if p != "index.html"]))
