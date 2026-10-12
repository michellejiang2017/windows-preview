# Verification

Checked on Windows x64, October 12, 2026.

- Native edition: **32** automated PDF/image, Qt usability and signature tests pass.
- Browser PDF engine: **12** tests pass for blank pages, order validation, insertion, duplication, deletion, rotation, extraction, undo, saveable PDFs and real PDFium object enumeration/transformation/deletion/text replacement. Object transformation checks also confirm a different page is unchanged.
- Browser interaction checks pass in Chrome for opening/rendering, blank page + undo, mouse selection/movement/resizing of an existing image, page number/label/bookmark dialogs, saved PDF reload, native text selection and a narrow mobile layout. No JavaScript page errors were reported.
- Additional Chrome checks pass for form values surviving serialization, drawn and typed signatures inserted as editable images, actual English OCR on a scanned invoice, and reviewed redaction rebuilding a page without its original text.
- Static bundle builds successfully with pinned dependencies. Hosting and release status are recorded in DEPLOYMENT.md.

## Run engine tests

```sh
cd web
pnpm test
pnpm build
```

## Browser integration checks

Install Playwright separately (`pnpm add -D playwright`) and ensure Chrome is installed. Then, from `web/`, run:

```sh
node test/browser.mjs
node test/advanced-browser.mjs
```

The scripts start and close their own local servers on ports 4174/4175. `PREVIEW_PLAYWRIGHT` can point to an existing Playwright package. The first OCR check downloads the English model and needs network access. Browser screenshots and an edited PDF are written to ignored `web/work/`.

## Native tests

```sh
python -m pip install -r desktop/requirements.txt pytest
python -m pytest desktop -q
```

Headless Qt checks use `QT_QPA_PLATFORM=offscreen`. Windows packaging is verified separately by the GitHub release workflow. Hardware printing, full OS shell integration, large or unusual documents, every browser and every available PDF field type have not been exhaustively tested. OCR may misrecognize words; inspect exports from complex PDFs.
