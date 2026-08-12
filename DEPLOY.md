# Deploying Hangry

Two services and a database: the API on Fly.io, the web app on Vercel,
Postgres wherever you like (Fly's managed Postgres is the shortest path).

Everything here needs your accounts, so these are commands for you to run.
The repo is already configured for them — `api/Dockerfile`, `api/fly.toml`,
and the environment variables below are in place and verified.

**Budget 45 minutes.** Do it before you need it. Discovering the deploy is
broken on a Sunday at 10pm costs the project; discovering it on a Tuesday
costs nothing.

---

## Order matters

There's a circular dependency, and it's the thing that wastes the hour:

- the **web app** needs the API's URL, baked in at build time
- the **API** needs the web app's origin, for CORS

So: deploy the API first, then the web app, then go back and tell the API
about the web app.

---

## 1. Install the CLIs

```bash
brew install flyctl && npm i -g vercel
```

```bash
flyctl auth login && vercel login
```

## 2. Launch the API (don't deploy yet)

From `api/`. The `--no-deploy` matters — the app needs a database attached
before its first boot, or the release command fails on connect.

```bash
cd api && flyctl launch --no-deploy
```

When it asks whether to overwrite `fly.toml`, **say no**. The committed one
already has the health check, the release command that runs migrations, and
`min_machines_running = 1`.

If it allocated a different app name than `hangry-api`, update the `app =`
line in `api/fly.toml` to match.

## 3. Create Postgres and attach it

```bash
flyctl postgres create --name hangry-db --region ewr --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1
```

```bash
flyctl postgres attach hangry-db --app hangry-api
```

`attach` sets `DATABASE_URL` on the app as a `postgres://` URL. You don't
need to convert it — `api/app/config.py` rewrites the scheme to the asyncpg
driver on load, which is verified by a unit test.

## 4. Deploy the API

```bash
flyctl deploy --app hangry-api
```

The release command runs `alembic upgrade head` before the new version takes
traffic. If migrations fail the deploy aborts and the old machine keeps
serving.

```bash
curl https://hangry-api.fly.dev/api/health
```

Expect `{"api":"ok","db":"ok"}`. If `db` says `unreachable`, the attach step
didn't take — check `flyctl secrets list --app hangry-api`.

## 5. Deploy the web app

From `web/`:

```bash
cd web && vercel link
```

```bash
vercel env add NEXT_PUBLIC_API_URL production
```

Paste your API origin — `https://hangry-api.fly.dev`, no trailing slash.

`NEXT_PUBLIC_*` variables are compiled into the bundle, so this must exist
*before* the build. Changing it later needs a redeploy, not a restart.

```bash
vercel --prod
```

## 6. Close the loop: tell the API about the web app

```bash
flyctl secrets set CORS_ORIGINS="https://your-app.vercel.app" --app hangry-api
```

Comma-separate to allow more than one origin (a custom domain, say). Setting
a secret restarts the machine on its own.

A missing origin here fails every browser request with a CORS error, which
in the UI is indistinguishable from the API being down — so if the deployed
site loads but nothing works, check this first.

## 7. Verify like a user

Not with curl. Open the site on your phone:

1. Create a group, share the link to yourself
2. Open it on a second device and join with a dietary constraint
3. Start a round, rank on both devices
4. Confirm the result names who the majority vote would have excluded

Then paste the group link into a group chat and check it unfurls with the
green preview card rather than a bare URL. That card is the only distribution
this product has.

---

## Custom domain (optional)

```bash
vercel domains add hangry.example.com
```

Then set both of these, or link previews keep pointing at the vercel.app
domain and CORS rejects the new one:

```bash
vercel env add NEXT_PUBLIC_SITE_URL production   # https://hangry.example.com
flyctl secrets set CORS_ORIGINS="https://hangry.example.com,https://your-app.vercel.app" --app hangry-api
```

---

## What will actually go wrong

| Symptom | Cause |
|---|---|
| Site loads, every action fails | `CORS_ORIGINS` missing the web origin (step 6) |
| `db: unreachable` on health | Postgres not attached, or attached to the wrong app |
| Deploy aborts in release phase | A migration failed — `flyctl logs` shows the SQL error |
| Links unfurl as bare URLs | `NEXT_PUBLIC_SITE_URL` unset on a custom domain |
| API calls hit localhost in prod | `NEXT_PUBLIC_API_URL` set after the build, so not baked in |
| First solve in a new city is slow | Cold geohash tiles. Overpass is being called; it's cached for 30 days after |

## Costs

Fly's shared-cpu-1x with 512MB and a 1GB Postgres volume sits in the
low single digits of dollars per month; Vercel's hobby tier is free for this.
`auto_stop_machines = "suspend"` idles the API when nobody's using it.

The one thing to watch is Overpass: it's free and unlimited but rate-limits
by IP, and every instance shares Fly's. The tile cache keeps it off the
request path, which is why it's there.
