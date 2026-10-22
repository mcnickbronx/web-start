# web-start

[Русский](readme.md) · **English**

A starter kit for web projects: a **Django + FastAPI** backend and a **Nuxt 4** frontend.

> The detailed documentation, the admin UI and API messages are in Russian. This page is
> a short English entry point; everything it links to is in Russian.

## Two roles

- **An engine for similar sites.** Sites differ in design and menus, while the blog, pages,
  forms, SEO and sitemap are shared. The shared part lives here and is released in versions;
  each site has its own repository with its design and pins an engine version.
- **A starting point for a standalone project** — a larger application with its own logic.
  Copy `back/` and `front/` and let the project live on its own.

## What's inside

| Folder | What |
|---|---|
| `back/` | Backend. Django — models, migrations, admin; FastAPI — the API under `/api`; Tortoise ORM — async access to the same tables. Modules `user`, `page`, `form`, `log` |
| `front/` | Site engine on Nuxt 4 and Nuxt UI 4: layers `core`, `form`, `page`, `user` and a demo site |

A backend module and a frontend layer with the same name are a pair (`page` ↔ `page`,
`form` ↔ `form`). They change together, so they live in one repository under one version.

- `user` — sign-up, sign-in, JWT with a session per device, password reset by email codes.
- `page` — pages and blog from the admin (Markdown editor, images), SEO, `sitemap.xml`, redirects.
- `form` — site forms: leads in the admin and by email, file uploads, captcha (simple math or Yandex SmartCaptcha).
- `log` — application log in the database, viewable in the admin.

## How it works

```
Site visitor (browser)
├─ opens a page ──→ site server: Nuxt + engine ──→ cache /_page-api ──→ API /api/page/…
├─ navigation, forms, sign-in, account ──────────────────────────────→ API /api/…
└─ images /media/… ──→ site server ──────────────────────────────────→ backend /media/…

Editor (browser) ──→ admin /admin

Backend: /api/* — FastAPI and Tortoise ORM, everything else — Django; one PostgreSQL database.
Emails and other slow work — background tasks (taskiq): in the API process or via Redis and a worker.
```

Why FastAPI next to Django, with a second ORM: an account page fires a dozen API requests,
and a synchronous stack runs out of connections and memory long before CPU. Django stays for
the admin and migrations; the API bypasses Django entirely and is truly async down to the
database. Measurements — [back/docs/benchmark.md](back/docs/benchmark.md).

## Quick start

Backend — Python 3.14 and PostgreSQL:

```bash
cd back
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.txt .env              # DEV=True, fill in DEV_DB_* for your local database
createdb project

cd app
python manage.py migrate
python manage.py sync_async_models
python manage.py createsuperuser
python manage.py runserver    # admin: http://127.0.0.1:8000/admin/, Swagger: /api/docs
```

Frontend demo site — Node.js 24:

```bash
cd front
npm install
cp .env.txt .playground/.env  # NUXT_PUBLIC_API_BASE — the backend address
npm run dev                   # http://localhost:3000
```

## A site on the engine

A new site starts from the template [web-site-starter](https://github.com/mcnickbronx/web-site-starter),
a starter for the site's front-end developer: build, deploy, header, footer and a lead form are already there. The site's `nuxt.config.ts`
pulls the engine at a version tag:

```ts
export default defineNuxtConfig({
  extends: [['gh:mcnickbronx/web-start/front#vX.Y.Z', { install: true }]],
})
```

The site brings its own layouts, pages and colors and may override engine components (not engine
pages); the engine brings data loading, SEO, forms and the blog. The site's backend is the Docker image of the same commit, built by
CI (`.github/workflows/back.yml`). The server setup (`back/compose.yml`) expects Traefik and
a few shared files: a server on [infra](https://github.com/mcnickbronx/infra) has all of them, for any other
server see [back/docs/deploy.md](back/docs/deploy.md#что-нужно-от-сервера).

One version for both parts — the repository tag. Major: a site has to change something by
hand; minor: new features, safe to update; patch: fixes. Changes — [CHANGELOG.md](CHANGELOG.md).

## Documentation (Russian)

- [readme.md](readme.md) — overview, versions, release process
- [back/readme.md](back/readme.md) — backend: structure, local run, modules; index of backend docs
- [back/docs/architecture.md](back/docs/architecture.md) — request path, two ORMs, pitfalls
- [front/readme.md](front/readme.md) — site engine, a site on the engine, layers
- `CLAUDE.md` files — code conventions; the project is developed with Claude Code

## License

[MIT](LICENSE)
