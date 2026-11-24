#!/usr/bin/env python3
"""Publish the site to Cloudflare using only the Cloudflare API (no wrangler).

  CLOUDFLARE_API_TOKEN=... python3 deploy.py            # live: fedenigro.com
  CLOUDFLARE_API_TOKEN=... python3 deploy.py --preview  # preview.fedenigro.com

Uploads public/ into a Workers KV namespace, uploads worker/index.js as the
Worker that serves it, and attaches fedenigro.com + www.fedenigro.com.
The token needs the "Edit Cloudflare Workers" permissions for the account
and the fedenigro.com zone.
"""
import base64, json, os, sys, uuid, urllib.request, urllib.error

ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "e514de0ba6f87affbae855c5d383de3e")
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or sys.exit("Set CLOUDFLARE_API_TOKEN")
PREVIEW = "--preview" in sys.argv
WORKER = "fedenigro-portfolio-preview" if PREVIEW else "fedenigro-portfolio"
KV_TITLE = WORKER + "-assets"
ZONE = "fedenigro.com"
HOSTNAMES = ["preview.fedenigro.com"] if PREVIEW else ["fedenigro.com", "www.fedenigro.com"]
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "public")
API = "https://api.cloudflare.com/client/v4"


def call(method, path, data=None, content_type="application/json"):
    if data is not None and content_type == "application/json":
        data = json.dumps(data).encode()
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"{method} {path} failed ({e.code}): {body[:800]}")


def kv_namespace():
    page = 1
    while True:
        res = call("GET", f"/accounts/{ACCOUNT}/storage/kv/namespaces?per_page=100&page={page}")["result"]
        for ns in res:
            if ns["title"] == KV_TITLE:
                return ns["id"]
        if len(res) < 100:
            break
        page += 1
    return call("POST", f"/accounts/{ACCOUNT}/storage/kv/namespaces", {"title": KV_TITLE})["result"]["id"]


def upload_files(ns):
    files = []
    for root, _, names in os.walk(PUBLIC):
        for n in names:
            full = os.path.join(root, n)
            files.append((os.path.relpath(full, PUBLIC).replace(os.sep, "/"), full))
    batch, size = [], 0
    def flush():
        if batch:
            call("PUT", f"/accounts/{ACCOUNT}/storage/kv/namespaces/{ns}/bulk", batch)
            print(f"  uploaded {len(batch)} files")
            batch.clear()
    for key, full in sorted(files):
        value = base64.b64encode(open(full, "rb").read()).decode()
        if size + len(value) > 40_000_000:
            flush(); size = 0
        batch.append({"key": key, "value": value, "base64": True})
        size += len(value)
    flush()
    # remove files that no longer exist in public/
    keep = {k for k, _ in files}
    old = [k["name"] for k in call("GET", f"/accounts/{ACCOUNT}/storage/kv/namespaces/{ns}/keys?limit=1000")["result"]
           if k["name"] not in keep]
    if old:
        call("POST", f"/accounts/{ACCOUNT}/storage/kv/namespaces/{ns}/bulk/delete", old)
        print(f"  removed {len(old)} old files")
    return len(files)


def upload_worker(ns):
    boundary = uuid.uuid4().hex
    meta = {"main_module": "index.js", "compatibility_date": "2026-11-01",
            "bindings": [{"type": "kv_namespace", "name": "ASSETS", "namespace_id": ns},
                         {"type": "plain_text", "name": "PREVIEW", "text": "1" if PREVIEW else ""}]}
    code = open(os.path.join(HERE, "worker", "index.js"), "rb").read()
    parts = [
        (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n'
         f'Content-Type: application/json\r\n\r\n').encode() + json.dumps(meta).encode() + b"\r\n",
        (f'--{boundary}\r\nContent-Disposition: form-data; name="index.js"; filename="index.js"\r\n'
         f'Content-Type: application/javascript+module\r\n\r\n').encode() + code + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    call("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{WORKER}", b"".join(parts),
         f"multipart/form-data; boundary={boundary}")


def attach_domains():
    zone_id = call("GET", f"/zones?name={ZONE}")["result"][0]["id"]
    for host in HOSTNAMES:
        call("PUT", f"/accounts/{ACCOUNT}/workers/domains", {
            "hostname": host, "service": WORKER, "zone_id": zone_id, "environment": "production"})
        print(f"  {host} -> {WORKER}")


if __name__ == "__main__":
    print("1/4 Storage"); ns = kv_namespace()
    print("2/4 Files"); n = upload_files(ns)
    print("3/4 Worker"); upload_worker(ns)
    if "--no-domains" in sys.argv:
        print("4/4 Domains skipped")
    else:
        print("4/4 Domains"); attach_domains()
    print(f"Done: {n} files published to https://{HOSTNAMES[0]}")
