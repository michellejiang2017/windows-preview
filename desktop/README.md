# Preview for Windows — PDF-focused v3

## Run

Install Python 3.12 (64-bit) from https://www.python.org/downloads/windows/ with the Python launcher enabled. Extract this ZIP into a writable folder and double-click **Run Preview.cmd**. First launch installs libraries; changed requirements trigger dependency updates.

On this computer, the separate **Launch Preview on this computer.cmd** reuses the installed workspace libraries. It depends on the workspace remaining in its current location and is not portable.

Alternatively:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Try **Demo.pdf**, with a scanned invoice, blank-page and redaction examples.

## Preview-style controls

The compact icon toolbar, thumbnail sidebar and neutral document canvas follow Apple Preview's layout. Click the markup icon to reveal editing tools. Hover an icon for its name. **Ctrl+S** saves the current file; **Ctrl+Shift+S** opens Save As. Existing PDF passwords are preserved when saving. Save As adds the extension automatically.

Choose **Edit objects**, click a text span or image, then drag to move or drag the lower-right handle to resize. Double-click for exact coordinates, replacement text/image, or deletion. Delete removes the selected object while the canvas has focus; selecting thumbnails switches deletion back to pages. Text editing is span-based and has the limitations below.

Choose **Select text**, drag across the page and press **Ctrl+C** to copy. The selection is highlighted on the page. Scans require OCR first.

Drop PDFs onto the canvas to insert after the current page, or onto the sidebar to choose the insertion location. Drop an image onto the canvas to place it on the page; drop onto thumbnails to insert an image page. Drop a file on an empty window to open it. Drag selected thumbnails to other apps as an extracted PDF.

## New PDF tools

The PDF menu includes local OCR; text/image object editing; blank-page review; scan straightening, contrast and grayscale; target-size compression; reviewed search-and-redact; side-by-side PDF comparison; bookmarks; page labels; headers, footers and numbering.

Use **Select text** in the markup toolbar to drag a text region and copy its extracted text. See **PDF-TOOLS.md** for full instructions and limitations. OCR skips pages already containing text. Text replacements use a standard font and do not reflow paragraphs. Complex image placements are refused. Scan cleanup flattens selected pages; run OCR afterward. Compression may rasterize pages. Comparison uses physical page positions.

## Existing tools

Ctrl/Shift-select thumbnails, drag to reorder, insert PDFs/images, add/replace/duplicate/delete/rotate pages, and extract selected pages with Ctrl+E. Save image sessions as PDFs. Ctrl+V places a clipboard image onto an existing page: drag its placement rectangle.

Markup includes text, pen, rectangles, highlights, crop and true redaction. Crop hides content; Redact removes underlying text/image data from the exported copy. Originals, undo snapshots and local backup versions may retain original content locally.

Fill forms; extract text/images; render pages; generate contact sheets; print; encrypt exports; inspect and remove metadata, annotations and links. Permission flags depend on the receiving viewer. Pen signatures are visual marks, not certified digital signatures.

Image tools include resize/rotate/color adjustments, collages, metadata removal, batch conversion and local background removal. First use of background removal downloads a roughly 5 MB model; OCR models are bundled with its installed library. No document upload or AI API key is required. Codec support varies; PSD is composite-only; RAW/OpenEXR and Photoshop layers are unsupported. Edited exports do not preserve C2PA manifests.

View controls include zoom, dark PDF appearance, canvas color, navigation history, repeat arrows and toolbar visibility. Drag file exposes a saved unmodified file to compatible Windows apps; selected thumbnails can be dragged out as an extracted PDF.

Overwriting an existing file backs up prior bytes under %LOCALAPPDATA%\PreviewWindows\versions. These backups have no automatic retention limit. Undo holds up to 20 snapshots and can use substantial memory for large files.

## Stack and scope

Native PySide6/Qt UI; PyMuPDF/MuPDF PDF engine; Pillow/pillow-heif image codecs; RapidOCR/ONNX Runtime local OCR; rembg local cutouts. At the user's request, 3D is excluded from the current interface and default dependencies.

Video evidence: [MacVince — Apple Preview is kinda insane](https://www.youtube.com/watch?v=FMiTNASBHiE), inspected creator chapters and English transcript. Historical mapping: FEATURES.md. Engine references: [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html), [RapidOCR](https://github.com/RapidAI/RapidOCR).

## Tests

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest test_preview.py test_pdf_tools.py test_usability.py -q
```

23 Windows automated tests passed, including real OCR and native dialog wiring. See TEST-RESULTS.md. Real-desktop clipboard, shell dragging, printing hardware, large files and exhaustive format compatibility still need broader testing.

## Licensing

Original source: AGPL-3.0-or-later. PyMuPDF/MuPDF requires AGPL compliance or commercial licensing. Qt/PySide6 and other dependencies retain their own terms. Review/include applicable licenses and notices before redistribution. See LICENSE.txt. No Apple or Adobe code/artwork is included.
