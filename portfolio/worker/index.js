// Serves the site from the ASSETS KV namespace (filled by deploy.py).
// Clean URLs: /about -> about.html, unknown paths -> 404.html.
const TYPES = {
  html: "text/html; charset=utf-8", css: "text/css; charset=utf-8", js: "text/javascript; charset=utf-8",
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  svg: "image/svg+xml", ico: "image/x-icon", pdf: "application/pdf", txt: "text/plain; charset=utf-8",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405 });
    }
    if (url.hostname.startsWith("www.")) {
      url.hostname = url.hostname.slice(4);
      return Response.redirect(url.toString(), 301);
    }
    let path = decodeURIComponent(url.pathname);
    if (path.length > 1 && path.endsWith("/")) {
      url.pathname = path.replace(/\/+$/, "");
      return Response.redirect(url.toString(), 301);
    }
    if (path.endsWith(".html")) {
      url.pathname = path === "/index.html" ? "/" : path.slice(0, -5);
      return Response.redirect(url.toString(), 301);
    }
    let key = path === "/" ? "index.html" : path.slice(1);
    if (!key.split("/").pop().includes(".")) key += ".html";

    let status = 200;
    let body = await env.ASSETS.get(key, "arrayBuffer");
    if (body === null) {
      key = "404.html";
      status = 404;
      body = await env.ASSETS.get(key, "arrayBuffer");
    }
    const ext = key.split(".").pop().toLowerCase();
    return new Response(request.method === "HEAD" ? null : body, {
      status,
      headers: {
        "content-type": TYPES[ext] || "application/octet-stream",
        "cache-control": ext === "html" ? "public, max-age=300" : "public, max-age=86400",
      },
    });
  },
};
