# fedenigro.com portfolio

The live site at https://fedenigro.com is the `portfolio/` folder of this repo.
(The rest of the repo is an older, unrelated Python project — leave it alone.)

- `portfolio/public/` — the site itself: plain HTML pages, `css/style.css`, `img/`, résumé PDF. No build step.
- `portfolio/worker/index.js` — small Cloudflare Worker that serves `public/` with clean URLs (`/about` → `about.html`).
- `portfolio/deploy.py` — publishes via the Cloudflare API (Python 3 stdlib only).
  In a cloud session the API key is injected by the network proxy, so run it with
  `CLOUDFLARE_API_TOKEN=proxy-injected`. Do not use `wrangler deploy`: its asset
  upload step fails behind the proxy.

## Change workflow (the owner is not technical — keep explanations plain)

1. The owner asks for a change. Make it on a new branch, matching the existing page markup and CSS.
2. Publish a private preview (the owner does NOT want a public preview address):
   `python3 portfolio/make_preview.py <scratchpad>/preview-site` builds a copy and prints the
   supporting-file list. Publish `<scratchpad>/preview-site/index.html` with the Artifact tool to the
   existing preview artifact **https://claude.ai/artifact/UotpQDiig7kUY1XPwHfNeU** (pass it as `url`,
   read it first; `root` = the preview-site folder, `files` = the printed list) so the link never changes.
   Send the owner that link and a short list of what changed. Nothing touches fedenigro.com yet.
3. Repeat until the owner says "merge". Then merge the branch into the main branch, push, and publish live:
   `CLOUDFLARE_API_TOKEN=proxy-injected python3 portfolio/deploy.py` → https://fedenigro.com
4. Check that the live pages load (curl the main URLs) and tell the owner it's live.

Page URLs must stay the same as the old Squarespace site (`/about`, `/udemy`, `/new-page-1`, …).
