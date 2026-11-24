# fedenigro.com — portfolio

Static portfolio site, moved over from Squarespace and hosted on **Cloudflare Workers (static assets)**.
No build step: what's in `public/` is what gets served.

```
public/
  index.html                 Work (home)
  about.html                 About
  new-page-1.html            Explicit Signal Collection (Skillshare)
  project-modal.html         Project Browsing Experience (Skillshare)
  user-management.html       Enterprise Team Management (Skillshare for Teams)
  udemy.html                 Augmenting Account Creation (Udemy)
  redbooth-freemium-1.html   Creating a Downgrade Experience (Redbooth)
  404.html
  css/style.css              All styles (colors and fonts are variables at the top)
  img/                       Images, one folder per page
  Federico_Nigro_Res_2025.pdf
```

The URLs match the old Squarespace site (`/about`, `/udemy`, …) so existing links keep working.

## Run locally

```bash
npm install
npm run dev        # http://localhost:8787
```

## Deploy

Current setup — straight from the Cloudflare API (needs only Python 3):

```bash
CLOUDFLARE_API_TOKEN=your-token python3 deploy.py
```

It uploads `public/` into a Workers KV store, uploads `worker/index.js` (the small
program that serves those files at clean URLs) and attaches fedenigro.com and
www.fedenigro.com. The token comes from the "Edit Cloudflare Workers" template.

Alternative — Cloudflare's built-in static assets (uses `wrangler.jsonc`).

Option A — from your machine:

```bash
npx wrangler login
npm run deploy
```

Option B — automatic deploys from GitHub: in the Cloudflare dashboard go to
Workers & Pages → Create → Import a repository, pick this repo, and set the
**root directory** to `portfolio`. Every push to the branch then redeploys.

## Point fedenigro.com at it

1. Add `fedenigro.com` to your Cloudflare account and switch the domain's nameservers to Cloudflare's (at your registrar).
2. In the Worker → Settings → Domains & Routes → Add → Custom domain: add `fedenigro.com` and `www.fedenigro.com`.
3. Once it's live, cancel the Squarespace site.
