# Felix Sargent's Personal Website

This repository contains the source code for my personal website, felixsargent.com. It's a static website built with Jekyll and deployed to Cloudflare Workers.

## Running Locally

The toolchain (Ruby 3.4, Node 22) and tasks are defined in `mise.toml`. Install [mise](https://mise.jdx.dev) once (`brew install mise` or `curl https://mise.run | sh`), then:

```bash
mise install      # Ruby and Node, precompiled, a few seconds
mise run serve    # http://localhost:4000 with live reload (bin/serve does the same)
```

Gems are installed into `vendor/bundle` automatically the first time any task runs.

| Task | What it does |
| --- | --- |
| `mise run serve` | Local preview with live reload, including drafts and future-dated posts |
| `mise run build` | Production build into `_site/` (also `bin/build`) |
| `mise run check` | Strict build that fails on bad front matter or Liquid errors |
| `mise run deploy` | Build, then `npx wrangler deploy` |
| `mise run clean` | Remove `_site/` and caches |

Repo-only files (this README, `article-ideas.md`, `bin/`, `mise.toml`, `wrangler.jsonc`) are excluded from the build in `_config.yml`, so they are not published.

## Deploying

The site is built with Jekyll and served by Cloudflare Workers static assets (`wrangler.jsonc` serves `_site/` on felixsargent.com and www). Pushes to `main` are built and deployed on Cloudflare's side; the old GitHub Actions workflow was removed in May 2026. The build command and settings live in the Cloudflare dashboard, not in this repo.

Cloudflare's build image reads `.ruby-version`, and so does mise locally, so bump Ruby there and both stay in step.

To deploy manually from a machine logged in with `npx wrangler login`:

```bash
mise run deploy
```
