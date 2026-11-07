# Hosting Lectern

Lectern runs locally by default, and the task does not require hosting. This page covers the case where reviewers or a team should reach it at a URL.

## What protects a hosted Lectern

A public URL attached to paid API keys is a bill waiting to happen, so a hosted Lectern should always set `ACCESS_TOKEN`.

| Protection | How it works | Setting |
|---|---|---|
| Access passphrase | Every `/api` call needs it. The browser enters it once and receives a hashed, HttpOnly, `SameSite=Strict` cookie (`Secure` over https). Scripts can send an `X-Lectern-Key` header. `/api/health` stays open for uptime checks and reveals no keys. | `ACCESS_TOKEN` |
| Spend limits | Per client: new lessons per hour, model-backed actions per hour (eight times the lesson limit) and requests per minute. Over the limit the API answers 429 with `Retry-After`. | `LESSONS_PER_HOUR` (30), `REQUESTS_PER_MINUTE` (240) |
| Real client addresses | Behind a host's proxy, limits count the `X-Forwarded-For` client, not the proxy. | `BEHIND_PROXY=true` |
| Passphrase guessing | Ten attempts per five minutes per client. | fixed |
| Browser hardening | Strict Content Security Policy (the interface loads nothing from other origins), `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy, and HSTS over https. | fixed |
| Request size | Bodies over 512 KB are refused. | fixed |
| Server-side fetching | Pages are fetched only from public addresses; private, loopback and cloud-metadata addresses are refused, including after redirects. | fixed |
| Secrets | Keys are read from the environment, never returned by the API, and excluded from the image by `.dockerignore`. | — |

The container runs as a non-root user and stores everything in `/app/data` (one SQLite file).

## Option 1: Docker on any machine

```bash
cp .env.example .env          # keys, plus ACCESS_TOKEN=<a long random phrase>
docker compose up --build -d  # http://localhost:8000
```

Put it behind any https reverse proxy (Caddy, nginx, Cloudflare Tunnel) and set `BEHIND_PROXY=true`.

## Option 2: Render (blueprint included)

1. Push the repository to GitHub.
2. In Render: **New → Blueprint**, choose the repository. `render.yaml` creates a Docker web service with a 1 GB disk at `/app/data`, generates `ACCESS_TOKEN`, and sets `BEHIND_PROXY=true` and `LESSONS_PER_HOUR=10`.
3. Enter the API keys when Render asks for them.
4. Open the service's **Environment** tab to read the generated `ACCESS_TOKEN`; give it only to the people who should use the tool.

A persistent disk needs a paid instance. On the free instance type, remove the `disk` block: Lectern still works, but lessons are lost when the instance restarts, so export what you want to keep.

## Option 3: Hugging Face Spaces (free)

Create a **Docker** Space, push this repository to it, and add the keys and `ACCESS_TOKEN` as Space secrets. Spaces expect port 7860, so also add the variable `PORT=7860`. Without persistent storage, export lessons you want to keep.

## Checking a deployment

```bash
curl https://your-host/api/health                                   # 200, "access_protected": true
curl -o /dev/null -w '%{http_code}\n' https://your-host/api/lessons # 401 without the passphrase
```

Then open the site, enter the passphrase and click **Check connections** on the home page: every service should show green.
