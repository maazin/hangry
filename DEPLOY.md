# Deploying Hangry

Three services, all with a web dashboard, all on a free plan, all connected to
GitHub. No terminal.

| Piece | Where | Cost |
|---|---|---|
| Database | [Neon](https://neon.tech) | Free |
| API | [Render](https://render.com) | Free |
| Web app | [Vercel](https://vercel.com) | Free |

Everything here happens in your accounts, so these are steps for you to click.
The repository already carries what each one reads: `render.yaml` for Render,
`api/Dockerfile` for the container, and the environment variables listed below.

**Budget 30 minutes.** Read the cold start note before you start, because it
shapes what you should expect the first time you open the link.

---

## Read this first: the free plan sleeps

Render's free web services stop after a stretch with no traffic and start again
on the next request. Waking takes roughly 50 seconds.

That collides with the whole idea of Hangry, which is that opening a link and
ranking takes half a minute. The first person to open a link after a quiet
period waits for the API to wake before anything appears.

Three ways to live with it:

1. **Accept it.** Fine while you are testing with friends who know to wait.
2. **Warm it.** A free uptime pinger hitting `/api/health` every 10 minutes
   keeps the service awake. [cron-job.org](https://cron-job.org) does this from
   a web dashboard and costs nothing.
3. **Pay to remove it.** Render's cheapest paid instance runs about seven
   dollars a month and never sleeps.

Option 2 is the sensible middle, and it is set up at the end of this guide.

Neon's free database also suspends when idle, though it wakes in under a
second, so it is not worth working around.

---

## Order matters

There is a loop in the setup, and it is what wastes the hour if you meet it by
surprise:

- the **web app** needs the API's address, and it is compiled in at build time
- the **API** needs the web app's address, for CORS

So the order is database, then API with a placeholder, then web app, then back
to the API to fill in the real value.

---

## 1. Database on Neon

1. Sign up at [neon.tech](https://neon.tech). No card is asked for.
2. Create a project. Any name and region will do, though a region near your
   users keeps queries quicker.
3. On the project dashboard, open **Connection Details** and copy the
   connection string. It starts with `postgresql://`.

Keep that string. It is a password, so treat it like one.

You do not need to convert it. The app rewrites the scheme to the async driver
when it loads, which a unit test covers.

## 2. API on Render

1. Sign up at [render.com](https://render.com) and connect your GitHub account.
2. Choose **New**, then **Blueprint**.
3. Pick the `maazin/hangry` repository. Render finds `render.yaml` and offers a
   service called `hangry-api` on the free plan.
4. It asks for the two values the blueprint left blank:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | The Neon string from step 1 |
   | `CORS_ORIGINS` | `http://localhost:3000` for now |

   The CORS value is a placeholder. Step 4 replaces it.

5. Choose **Apply**. The first build takes a few minutes, since it builds the
   container from scratch.

Migrations run when the container starts, so the database sets itself up on
first boot. Render then polls `/api/health`, which opens a real database
connection, so a wrong `DATABASE_URL` fails the deploy instead of going live
broken.

When it finishes, open the service URL and add `/api/health`:

```
https://hangry-api.onrender.com/api/health
```

You want `{"api":"ok","db":"ok"}`. If `db` says `unreachable`, the Neon string
is wrong or incomplete. Copy it again.

## 3. Web app on Vercel

1. Sign up at [vercel.com](https://vercel.com) and connect GitHub.
2. Choose **Add New**, then **Project**, and import `maazin/hangry`.
3. Set **Root Directory** to `web`. This is the step people miss, and without
   it the build fails looking for a Next.js app at the repository root.
4. Open **Environment Variables** and add one:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | Your Render URL, for example `https://hangry-api.onrender.com` |

   No trailing slash. Anything starting `NEXT_PUBLIC_` is compiled into the
   browser bundle, so it has to exist before the build rather than after.

5. Choose **Deploy**.

Vercel gives you a domain such as `hangry-xyz.vercel.app`. Copy it.

## 4. Close the loop

Back in Render, open the service, then **Environment**, and change
`CORS_ORIGINS` to your Vercel domain:

```
https://hangry-xyz.vercel.app
```

Saving restarts the service on its own. Separate several origins with commas
if you add a custom domain later.

Skipping this makes every action in the deployed site fail, which looks exactly
like the API being down. If the site loads and nothing works, look here first.

## 5. Keep it awake, at no cost

1. Sign up at [cron-job.org](https://cron-job.org).
2. Create a job pointing at `https://hangry-api.onrender.com/api/health`.
3. Run it every 10 minutes.

Render's free plan gives 750 instance hours a month, and one service kept awake
sits inside that.

## 6. Check it the way a person would

Use your phone rather than the dashboard.

1. Create a group and send yourself the link.
2. Open it on a second device and join with a dietary restriction set.
3. Start a round and rank on both devices.
4. Confirm the result names whoever a majority vote would have excluded.

Then paste the group link into a group chat and check that it unfurls as a
preview card rather than a bare URL. That card is the only way this product
spreads.

---

## Custom domain, still free

Vercel includes custom domains on the free plan. Add yours under
**Settings**, then **Domains**, and point your DNS as instructed.

Two values then need updating, or link previews keep naming the old domain and
CORS rejects the new one:

- in Vercel, add `NEXT_PUBLIC_SITE_URL` set to `https://yourdomain.com`, then
  redeploy
- in Render, set `CORS_ORIGINS` to `https://yourdomain.com,https://hangry-xyz.vercel.app`

---

## What actually goes wrong

| Symptom | Cause |
|---|---|
| First load takes about a minute | Render free plan waking up. See step 5 |
| Site loads, every action fails | `CORS_ORIGINS` does not match the Vercel domain |
| `db: unreachable` on health | The Neon connection string is wrong or truncated |
| Vercel build cannot find the app | **Root Directory** is not set to `web` |
| API calls go to localhost in production | `NEXT_PUBLIC_API_URL` was added after the build. Redeploy |
| Links unfurl as bare URLs | `NEXT_PUBLIC_SITE_URL` unset on a custom domain |
| First search in a new city is slow | Cold map tiles. Overpass is being queried, and the result is cached for 30 days |

## Data retention

The interface tells people their rounds delete themselves. The API keeps that
promise on a timer, with no setup needed: expired rounds and everything
attached to them are removed every hour, and groups nobody has opened for 90
days go too. `GROUP_RETENTION_DAYS` and `PURGE_INTERVAL_MINUTES` change those
windows from the Render dashboard.

Crawlers are told to stay out of `/g/` and `/s/` in `web/app/robots.ts`. Those
links are unlisted rather than private, and a search index would make them
neither.

## If the cold start becomes the problem

`api/fly.toml` is committed for [Fly.io](https://fly.io), which keeps a machine
warm and runs migrations as a proper release step, so a failed migration aborts
the deploy. It needs a card and the CLI. Everything else in the repository is
the same.
