# Deploying ApexWMS

The whole system runs from one `docker-compose.prod.yml`: Postgres, a one-shot
migration job, the FastAPI backend, and the Next.js frontend. The same file runs
locally for a pre-deploy check.

## Images

- `backend/Dockerfile` — multi-stage, `uv sync --no-dev`, runs as a non-root user,
  serves `uvicorn main:app` with `WEB_CONCURRENCY` workers. The `apexwms` ops CLI
  is on `PATH` inside the container.
- `frontend/Dockerfile` — multi-stage, Next.js `output: "standalone"`, non-root,
  `node server.js` on port 3000.

Both build contexts are the repo root (the backend is a uv workspace).

## Local check before deploying

```bash
cp .env.prod.example .env.prod
# edit .env.prod: set POSTGRES_PASSWORD, APEXWMS_JWT_SECRET; keep FRONTEND_PORT=127.0.0.1:3000

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

The `migrate` job runs the master schema then every tenant DB, then `backend`
starts. Create an operator and a first store:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend \
  apexwms create-superadmin --email you@example.com --name "You"

docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend \
  apexwms create-tenant --name "Acme Phones" --slug acme \
    --owner-email owner@acme.test --owner-name "Acme Owner"
```

Open http://localhost:3000 and log in with the printed temporary password.
Health: `curl localhost:3000/api/backend/... ` goes through the BFF;
the backend's own check is `docker compose ... exec backend python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')"`.

Tear down (keeps the database volume): `docker compose -f docker-compose.prod.yml --env-file .env.prod down`.
Add `-v` to also wipe Postgres data.

## On the server

Same steps. Pick one of the two ways to expose it.

### Option A — Caddy in compose (automatic HTTPS)

Point your domain's A record at the server, then set `CADDY_DOMAIN` and
`CADDY_EMAIL` in `.env.prod` and start with the `edge` profile:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile edge up -d --build
```

Caddy gets a Let's Encrypt certificate on first request and proxies `:443` to the
frontend. Nothing else to configure. Keep `FRONTEND_PORT=127.0.0.1:3000` so the
app is not also reachable on plain HTTP.

### Option B — your own nginx on the host

Leave the `edge` profile off. The frontend is on `127.0.0.1:3000`. Example server
block:

```nginx
server {
    listen 443 ssl;
    server_name wms.example.com;

    ssl_certificate     /etc/letsencrypt/live/wms.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wms.example.com/privkey.pem;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The browser only ever talks to the frontend; the backend stays on the internal
compose network and is never published.

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

New migrations run automatically via the `migrate` job before the new backend
starts.

## Backups

```bash
./scripts/backup-db.sh /var/backups/apexwms
```

Dumps master + every tenant database + roles to one gzipped file. Restore
instructions are in the script header. Schedule it with cron.

## Production notes

- `APEXWMS_DEBUG=false` (default in the example) — no tracebacks in responses.
- Postgres is not published to the host. To inspect it: `docker compose ... exec postgres psql -U apexwms`.
- Secrets live only in `.env.prod`, which is git-ignored. Keep a copy somewhere safe.
- Rotating `APEXWMS_JWT_SECRET` logs everyone out.
