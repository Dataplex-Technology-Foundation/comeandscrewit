## Docker deployment (comeandscrewit.com)

Build and run locally:
```
docker compose up -d --build
```
Serves on `http://localhost:8093` via nginx:alpine (see `Dockerfile`, `nginx.conf`).
Smoke-tested 2026-08-13: `/`, `/faq.html`, `/contact.html`, `/robots.txt` → 200; unknown paths → 404 (custom `404.html`).

To deploy on the domain:
1. Point `comeandscrewit.com` (and `www`) A/AAAA or CNAME records at the container host.
2. On the host: `git clone` this repo, `docker compose up -d --build`, then front it with a TLS-terminating reverse proxy (e.g. Caddy, Traefik, or nginx-proxy) mapping port 443 → container port 80. This repo's own nginx serves plain HTTP only — TLS termination is out of scope here.
3. Before going live, verify the real domain value is set correctly in canonicals, OG tags, `robots.txt`, and `sitemap.xml`.

DNS/hosting-provider execution itself is out of scope for this pipeline run — only the container build/serve path.
