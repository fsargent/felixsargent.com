# Felix Sargent's Personal Website

This repository contains the source code for my personal website, felixsargent.com. It's a static website built with Jekyll and deployed to Cloudflare Workers.

## Running Locally

To preview the website locally, you'll need to have Ruby and Bundler installed.

1.  **Install Jekyll and other dependencies:**

    ```bash
    bundle install
    ```

2.  **Start the Jekyll server:**
    ```bash
    bundle exec jekyll serve --livereload
    ```

This will start a local server at `http://localhost:4000`. Any changes you make to the files will automatically reload the page.

## Deploying

The site is built with Jekyll and served by Cloudflare Workers static assets. The Worker configuration is in `wrangler.jsonc`.

GitHub Actions deploys pushes to `main` using `.github/workflows/deploy-worker.yml`. Configure these repository secrets before deploying:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Disable GitHub Pages for this repository after the first successful Workers deploy, then point `felixsargent.com` and `www.felixsargent.com` at the Worker routes configured in `wrangler.jsonc`.

To deploy manually from a machine authenticated with Wrangler:

```bash
bundle exec jekyll build
npx wrangler deploy
```
