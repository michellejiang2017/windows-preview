# Deployment

## Browser app

Public app: https://michellejiang2017.github.io/windows-preview/

GitHub Pages publishes the tested browser build automatically on pushes to `main`. No ChatGPT login is required. The repository is public and Pages is configured to deploy through GitHub Actions.

Alternative hosts: import this repository into Netlify (uses `netlify.toml`) or Vercel (uses `vercel.json`, repository root). Connecting either hosting account is required for deployment there. Both configurations build the same static app.

Private Sites copy: https://windows-preview-michelle.chummyquail32.chatgpt.site

The initial Sites deployment is private to the owner. App files are hosted; document processing remains in the browser. Hosting authentication may require a first online visit before offline use. PDF documents are not uploaded to hosting.

The tracked source is `web/`; build with `pnpm build`. Deploy `web/dist` as static files with MIME types for `.mjs`, `.js` and `.wasm`. Keep assets in the same relative directory. The service worker caches the app on first successful visit. Change the cache version in `public/sw.js` when publishing updated app code. OCR additionally needs its language model downloaded on first use.

Sites publication uses a separate deployment checkout with `.openai/hosting.json`. That generated checkout and temporary write credentials do not belong in this public GitHub repository. A GitHub push runs checks and builds an artifact; it does not automatically publish a new Sites version.

## Windows releases

Push a version tag such as `v0.4.0` to trigger `.github/workflows/windows.yml`. It tests the native edition, bundles `Preview.exe` and publishes `Preview-Windows.zip` to GitHub Releases. Workflow runs may take several minutes. The **Build Windows app** workflow can also be started manually to create a downloadable artifact. These builds are unsigned portable apps.

## Local desktop source

Use `desktop/Run Preview.cmd`. It detects an existing virtual environment or an available bundled runtime, otherwise it requires Python 3.12. Missing runtime errors are reported before attempting dependency installation.
