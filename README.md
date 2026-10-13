# Windows Preview

A Preview-inspired PDF and image workspace for Windows and the web. Original UI and icons; not affiliated with Apple or Adobe.

## Document Q&A portfolio app

[Passage](https://passage-document-qa.onrender.com) is a separate free Python document Q&A service with PDF/text/CSV ingestion, Chroma vector retrieval and extractive answers with source citations. See [setup, architecture and limitations](rag/README.md) and [cloud evaluation results](rag/reports/evaluation-cloud.json). Preview's existing editors continue to process documents locally; Passage uploads are sent to its server and expire with the demo session.

## Web app

Open the [public web app](https://michellejiang2017.github.io/windows-preview/) — no ChatGPT login required. Documents are processed on your device. Enable the pencil toolbar, select a PDF object, and drag to move or drag its lower-right corner to resize. Double-click text to replace it. Use the property panel for precise dimensions or deletion. See [DEPLOYMENT.md](DEPLOYMENT.md) for hosting details.

The thumbnail sidebar supports Ctrl/Command or Shift selection, drag-to-reorder, blank page insertion, duplication, deletion and rotation. Drop PDFs into the sidebar to insert pages; drop an image onto the canvas to place it. Images can also become PDF pages. Select text to copy normally; Ctrl+S saves or downloads your edited PDF.

To install the browser edition as a desktop app, use Edge/Chrome's **Apps → Install this site as an app**. The web app caches its code for offline use. English OCR downloads a recognition model on first use. Documents are not uploaded, synced or saved in browser storage, and closing the app discards unsaved work.

### Develop locally

Install Node.js 24 and pnpm 11.25.0, then:

```sh
cd web
pnpm install --frozen-lockfile
pnpm test
pnpm build
pnpm dev
```

Open http://127.0.0.1:4173. `web/dist` is a static site and can be hosted on any HTTPS static host; no PDF processing server or paid API is needed.

## Native Windows app

Download **Preview-Windows.zip** from [Releases](https://github.com/michellejiang2017/windows-preview/releases), extract, and run `Preview.exe` when a release build is available. Releases are built by the Windows workflow when a version tag is pushed. The standalone build includes its Python runtime.

To run from source, install Python 3.12 and double-click `desktop/Run Preview.cmd`. First launch installs its libraries. Or create a virtual environment and install `desktop/requirements.txt`, then run `desktop/app.py`.

## Signatures and markup

Click the pencil toolbar, then **Sign**. Draw a signature with a mouse/touch/pen, or type your name. Place it on the PDF, move or resize it, and Save. Signatures are not retained outside the current document. This creates a visible signature; certificate-based digital signing is not included. The native edition has **Edit → Signature** and a signature button in its markup toolbar. Both editions also provide pen drawings, text, shapes and highlights.

## Features and limits

| PDF workflow | Browser | Native Windows |
| --- | --- | --- |
| Blank pages, merge/insert, reorder, duplicate, delete, rotate, extract | Yes | Yes |
| Existing PDF objects: move, resize, delete | Text, images, paths, grouped objects via PDFium | Text spans and direct images |
| Replace existing text | Uses original font; missing characters may not be supported | Standard font; no paragraph reflow |
| Add/paste/drop images, text, pen, shapes, highlights | Yes | Yes |
| Draw/type/place visual signatures | Yes | Yes |
| Text selection, text extraction, raster image extraction, PNG export | Yes | Yes |
| Scanned-page OCR | English printed text, one page at a time | English/Chinese, selected/all pages |
| Redaction / reviewed search-redact | Affected pages rasterized and rebuilt | Removes underlying PDF content |
| Blank-page review, scan cleanup | Reviewed detection; contrast/grayscale/manual straightening | Reviewed detection; automatic straightening |
| Compress PDF, compare versions | Image-page compression; visual page comparison | Target-size attempts; text/image comparison |
| Fill forms, page labels, bookmarks, page numbers, metadata | Common text/check/dropdown fields; add labels/bookmarks/numbers | Advanced dialogs |
| Password-protected PDF editing/encrypted export | Not supported | Yes |
| Image adjustments, background removal, batch conversion | Not included yet | Yes |
| 3D | Excluded | Excluded |

Redaction rebuilds affected pages without original text or image resources; cropping merely hides content. Undo history and original files retain original information. Browser compression and scan cleanup flatten text, annotations, links and forms on affected pages. Search-redact finds phrases within PDF text segments, not across segment boundaries. Comparison uses physical page positions, not semantic alignment. Review exports from complex PDFs. Object groups are moved as a group, and text replacement does not reflow surrounding paragraphs. No certified digital signatures or full Adobe suite parity is claimed.

## Architecture

`desktop/` contains the native PySide6/PyMuPDF app. `web/` uses PDF.js for rendering and selectable text, PDF-lib for page/document assembly, PDFium WebAssembly for existing object changes, and Tesseract.js for local OCR. Browser and native engines differ; they exchange standard PDF files. The web edition uses no cloud PDF backend.

## Verification and deployment

See [TESTING.md](TESTING.md) for checks and [DEPLOYMENT.md](DEPLOYMENT.md) for release/hosting details. GitHub Actions tests/builds the browser bundle on push and packages the Windows app on version tags or manual workflow runs.

## License

AGPL-3.0-or-later for original project code, as established by the original desktop project. Third-party dependencies retain their own licenses. See [LICENSE](LICENSE) and their package notices.
