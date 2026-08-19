# Deploying techtree.sh on Fly.io

The commands that take this repository from nothing to `https://techtree.sh`
answering, in order, with the point of no return marked.

This page is about *hosting*. It creates a box, a database, a certificate, and
DNS. What the box **publishes** is decided in [runbook.md](runbook.md), and
deploying does not decide it: a deploy migrates and starts, and the site keeps
serving exactly what it was serving. Importing and moving the pointer are
separate commands, run on purpose, and they are the last two sections here.

The important consequence: **everything up to and including the first deploy is
safe before Gate 2.** It stands up the hosting with the declared *placeholder*
release active — the same thing the development database serves today — so the
box, the database, the certificate, and the DNS can all be proved before the
founder is asked to approve anything. Do it in that order.

## What is already decided

| | | why |
| --- | --- | --- |
| Fly app | `techtree-sh` | free on the platform as of 2026-08-19 (`flyctl status -a techtree-sh` reports no such app) |
| Organization | `regent` | the slug `flyctl orgs list` reports for the org displayed as "Regent". **Not** `regents` |
| Postgres app | `techtree-sh-db` | one cluster, one consumer, named after it |
| Primary region | `iad` | the org's other production apps already run there, and Ashburn is Fly's largest US-East region. The surface is read-only behind an anycast proxy, so one region is enough |
| Machine | shared CPU, 1 vCPU, 512 MB | the site serves files it already has and a handful of small reads. 256 MB is under what the BEAM plus a 10-connection pool wants during a release command; 512 MB is the next size up and leaves headroom without paying for a second core |
| Internal port | 8080 | `PORT` in `fly.toml`, `internal_port` in `[http_service]`, Bandit binds it |
| Health check | `GET /healthz` | it answers 200 only when there is an active, completed release, so an unimported machine is correctly not sent traffic |
| Image | `Dockerfile` at the repository root | Elixir 1.19.5 / OTP 28.2 / Debian trixie, matching this repository's toolchain |

## Before you start

1. `flyctl auth whoami` — logged in.
2. `flyctl orgs list` — `regent` is listed.
3. The catalog bundle exists in the working tree. It is generated, not
   committed, and it is what the image publishes:

       mix catalog.verify

   If `priv/catalog` is absent or stale, sync it first — the placeholder
   bootstrap, not the candidate:

       mix run scripts/sync_catalog.exs \
         --source ../techtree-python/src/techtree/resources/catalog \
         --source-revision <full commit> \
         --generator-version <version> \
         --bootstrap priv/bootstrap/development.json

   `.dockerignore` deliberately lets `priv/catalog` and `priv/release` into the
   build context even though git ignores them. A build without them produces an
   image that serves nothing.

## Part 1 — hosting, safe before Gate 2

### 1. Create the app

    flyctl apps create techtree-sh --org regent

### 2. Create the database

    flyctl postgres create \
      --name techtree-sh-db \
      --org regent \
      --region iad \
      --initial-cluster-size 1 \
      --vm-size shared-cpu-1x \
      --volume-size 1

Single node, smallest machine, 1 GB volume. No backups are requested, and that
is deliberate rather than thrifty: every row in this database is reproduced
exactly by importing the bundle the image already carries, so a backup would
restore something the image can rebuild.

The command prints a superuser password once. Save it somewhere the founder can
reach; it is not recoverable.

### 3. Attach it

    flyctl postgres attach techtree-sh-db --app techtree-sh

This creates a database and a role for the consuming app and sets `DATABASE_URL`
as a secret on `techtree-sh`. Do not set `DATABASE_URL` by hand — attach owns it.

The URL points at the cluster over the organization's private network, which is
IPv6 only. `fly.toml` sets `ECTO_IPV6 = "true"` for that reason.

### 4. Set the remaining secrets

    flyctl secrets set --app techtree-sh \
      SECRET_KEY_BASE="$(mix phx.gen.secret)" \
      PHX_HOST="techtree-sh.fly.dev"

`PHX_HOST` is deliberately the Fly hostname for now. Every absolute URL the site
prints, and the origin its live pages are allowed to connect from, is built from
it — so while the smoke test runs against `techtree-sh.fly.dev`, that is what it
should say. Step 11 changes it to `techtree.sh` once the certificate is issued.

There is no `TECHTREE_BOOTSTRAP_CHANNEL`. Unset, the release serves the
`development` channel, whose staged release is the declared placeholder. See
"The channel variable" below before setting it to anything.

### 5. Deploy

    flyctl deploy --app techtree-sh --remote-only --ha=false --strategy immediate

- `--remote-only` builds on Fly's x86-64 builder. An Apple-silicon laptop
  building locally produces an arm64 image that Fly's machines cannot run.
- `--ha=false` creates one machine rather than the default two.
- `--strategy immediate` for **this deploy only**. `release_command` runs the
  migrations, and then the machine starts with an empty database and correctly
  reports 503 at `/healthz` — it has nothing true to publish yet. There is
  nothing for a health check to wait for until step 6. Later deploys use the
  default rolling strategy and are gated on the check properly.

### 6. Import the release the image carries

    flyctl ssh console --app techtree-sh

then, at the prompt:

    /app/bin/techtree eval 'Techtree.Release.import_catalog()'
    exit

As a single command instead:

    flyctl ssh console --app techtree-sh \
      --command "/app/bin/techtree eval 'Techtree.Release.import_catalog()'"

It prints the catalog digest and the channel. The import stages the bundle's
bootstrap release and publishes it. Before Gate 2 that release is the declared
placeholder, so the public install flow stays shut — which is the whole point of
being able to do this early.

### 7. Confirm the machine is healthy

    flyctl status --app techtree-sh
    flyctl checks list --app techtree-sh
    curl -s https://techtree-sh.fly.dev/healthz

`/healthz` must now be 200 and name channel `development`, catalog digest
`sha256:62714b77…`, import status `complete`.

### 8. Allocate the addresses DNS will point at

    flyctl ips list --app techtree-sh

If the list is missing either family:

    flyctl ips allocate-v4 --shared --app techtree-sh
    flyctl ips allocate-v6 --app techtree-sh

The shared IPv4 is free and works for a custom domain, apex included — Fly's
proxy routes on the hostname. If it ever misbehaves, a dedicated IPv4 is
`flyctl ips allocate-v4 --app techtree-sh` (no `--shared`) and costs about $2 a
month.

### 9. Ask Fly for the certificate

    flyctl certs add techtree.sh --app techtree-sh
    flyctl certs check techtree.sh --app techtree-sh

**`flyctl certs check` prints the definitive records.** The table below is the
shape to expect; where the two disagree, the command is right and this page is
stale.

### 10. Add the DNS records in Vercel

Vercel dashboard → the `techtree.sh` domain → **DNS Records** → Add.

Apex, using the addresses from step 8:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| `A` | `@` | the IPv4 from `flyctl ips list` | 60 |
| `AAAA` | `@` | the IPv6 from `flyctl ips list` | 60 |

Optional `www`:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| `CNAME` | `www` | `techtree-sh.fly.dev` | 60 |

Fly can also validate ownership by DNS challenge instead, which is the path to
use if the certificate must exist before any traffic is pointed at it:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| `CNAME` | `_acme-challenge` | the target `flyctl certs check` prints | 60 |

Two things to expect from Vercel specifically:

- Vercel DNS has no apex `CNAME`. The apex must be `A` + `AAAA`, which is what
  Fly wants anyway.
- If `techtree.sh` is currently assigned to a Vercel *project*, Vercel keeps its
  own apex record and will refuse or override yours. Remove the domain from the
  project first, keeping it in the account's DNS.

Raise TTL to 3600 once the records are proved.

Then wait for issuance:

    flyctl certs check techtree.sh --app techtree-sh

### 11. Point the app at its real hostname

    flyctl secrets set --app techtree-sh PHX_HOST=techtree.sh

This restarts the machine. Nothing is imported and no pointer moves.

If `www.techtree.sh` was added in step 10, note that the live pages accept a
socket connection only from the host `PHX_HOST` names. `www` will serve pages
that render but do not connect. Serving the apex only, and leaving `www` to a
redirect at the DNS/registrar layer or not at all, avoids the question entirely
— that is the recommendation for v0.1.

### 12. Smoke-test the published surface

    curl -s https://techtree.sh/healthz

    curl -sD- https://techtree.sh/api/v1/catalog -o /dev/null

    curl -sD- https://techtree.sh/api/v1/bootstrap -o bootstrap.json
    shasum -a 256 bootstrap.json

    curl -s -o /dev/null -w '%{http_code}\n' -X POST https://techtree.sh/api/v1/bootstrap

    curl -sI http://techtree.sh/healthz

Expected before Gate 2:

| Check | Expected |
| --- | --- |
| `/healthz` | 200, channel `development`, catalog `sha256:62714b77…`, status `complete` |
| `/api/v1/catalog` | 200, `application/json` |
| `/api/v1/bootstrap` | `ETag` and body digest both `sha256:9e5afcb3…` — the placeholder |
| `POST /api/v1/bootstrap` | `405` with `Allow: GET, HEAD` |
| plain `http://` | a redirect to `https://`, with `strict-transport-security` |

Also worth one look: `https://techtree.sh/api/v1/objects/sha256:2aff2707…`
returns the starter Skill as `text/markdown; charset=utf-8`.

**Stop here until Gate 2.** The site is up, the certificate is real, the
database is migrated, and what is published is the placeholder.

## Part 2 — activation. GATE 2 ONLY

Nothing below runs before the founder has approved the candidate. Each step is
reversible by the pointer move in [rollback.md](rollback.md), but the point of
the gate is not to rely on that.

The candidate is `priv/releases/climb-v0.1.0/`. Its bootstrap release is
`sha256:57f95dccba41067e7e6a3c8bf7fc2dfdf897b9712e83823c5cda202c242bef89`, and
this build has never staged it.

### 13. Build the bundle that carries the candidate — founder approval required

In the repository:

    mix run scripts/sync_catalog.exs \
      --source ../techtree-python/src/techtree/resources/catalog \
      --source-revision <full commit> \
      --generator-version <version> \
      --bootstrap priv/releases/climb-v0.1.0/bootstrap.json

    mix catalog.verify

    shasum -a 256 priv/catalog/bootstrap.json

The last command must print `57f95dcc…`. The approved bytes are copied, never
rewritten; a different digest here means something regenerated them and the
approval no longer covers what is about to ship.

### 14. Deploy that image

    flyctl deploy --app techtree-sh --remote-only --ha=false

Default rolling strategy now: the health check gates it, and the running machine
keeps serving the placeholder until the new one is healthy.

Deploying still publishes nothing. The new image *carries* the candidate; the
database still has the placeholder active.

### 15. Stage and publish the candidate — the point of no return

    flyctl ssh console --app techtree-sh
    /app/bin/techtree eval 'Techtree.Release.import_catalog()'

The import stages the candidate and publishes it in the same transaction, which
is the activation. On any failure the placeholder keeps serving.

If the candidate is already staged from an earlier attempt and only the pointer
needs to move, that is the explicit form:

    /app/bin/techtree eval 'Techtree.Release.publish_bootstrap("sha256:57f95dccba41067e7e6a3c8bf7fc2dfdf897b9712e83823c5cda202c242bef89")'

### 16. Verify what is published

    curl -sD- https://techtree.sh/api/v1/bootstrap -o bootstrap.json
    shasum -a 256 bootstrap.json

`ETag` and body digest must both be `sha256:57f95dcc…`, and must equal the
digest in `priv/releases/climb-v0.1.0/checksums.json`. Then re-run the whole of
step 12; the 405 and the redirect must be unchanged.

## Rolling back

The placeholder stays staged forever, so going back is one command:

    flyctl ssh console --app techtree-sh
    /app/bin/techtree eval 'Techtree.Release.list_bootstrap_releases()'
    /app/bin/techtree eval 'Techtree.Release.publish_bootstrap("sha256:9e5afcb33633a702e106b5379a75f3a7cca250239b5fa08b228843cb61a2b9da")'

Nothing is deleted, nothing is rewritten, and nothing on anyone's machine is
touched. The full reasoning is in [rollback.md](rollback.md).

Note that a later `import_catalog()` publishes whatever bootstrap the deployed
image carries, and would undo this. After a rollback, redeploy the image built
in step 5 before importing again.

## The channel variable

`TECHTREE_BOOTSTRAP_CHANNEL` selects the release channel the site imports and
serves. Unset, it stays on the compile-time default, `development`.

**Do not set it to `stable` today.** Every bundle in this repository — the
placeholder and the approved candidate alike — declares `"channel":
"development"`, and the importer refuses a bundle whose channel does not match
the one the build serves. Setting `stable` produces two things, both verified:

- `import_catalog()` raises `the bundle publishes a different release channel
  than this build serves` and writes nothing, and
- the running site reports 503 at `/healthz` with `channel: "stable"`, because
  nothing is active on a channel nothing was ever imported into. The machine
  then fails its health check.

Both failures are safe — no data is written and no pointer moves — but the site
goes dark. Moving to a `stable` channel means regenerating the bundles to
declare it, which changes the candidate's digest and therefore changes what the
founder approved. That is a Gate-2 decision, not a deploy setting.

## Who has to say yes

| Step | Approval |
| --- | --- |
| 1–12 — create app, database, deploy, import placeholder, DNS, certificate, smoke test | Safe before Gate 2. Spends about $5 a month and publishes only the placeholder |
| 13–14 — build and deploy the image carrying the candidate | Founder approval. The approved bytes are on the host but not yet served |
| 15 — import / publish | **Founder approval. This is activation.** The public install flow opens here |
| Rollback | No approval needed. Moving back to the placeholder is always allowed |

## Notes for whoever runs this

- `bin/server` is the only entry point that sets `PHX_SERVER`. That is why
  `bin/migrate` and every `bin/techtree eval` can run on a machine that is
  already serving without a second process fighting for the port. Do not add
  `PHX_SERVER` to `fly.toml`.
- The health check sends `Host: localhost` on purpose. It connects to the
  container directly, past the proxy that terminates TLS, so without that host
  `:force_ssl` answers it with a 301 and the machine never goes healthy.
- `fly.toml` has no `[[statics]]` block on purpose. Fly's proxy would serve
  `priv/static` itself and skip the endpoint, and with it the content-security,
  nosniff, frame, and referrer headers this application attaches to every static
  file.
- `flyctl logs --app techtree-sh` for anything that goes wrong at boot. A
  missing `PHX_HOST`, `SECRET_KEY_BASE`, or `DATABASE_URL` stops the release
  before it starts, by name, rather than booting into a wrong guess.
