# PDF tools added in v2

All tools are under the **PDF** menu. Operations run locally; no document is uploaded and no paid API is required. Select multiple thumbnails with Ctrl/Shift. Editing operations support Undo; exported comparison reports and compressed copies are separate files.

## OCR

Choose **OCR selected pages** or **OCR whole document**. RapidOCR's packaged ONNX models recognize scanned pages and insert an invisible text layer. Appearance stays unchanged. Use Find, Extract text, or the **Select text** toolbar tool: drag a region, then press Ctrl+C to copy the highlighted text. The default OCR models recognize English and Chinese. OCR may make mistakes; pages already containing text are skipped to avoid duplicates. Mixed pages containing existing text plus scanned text require a future selective OCR mode. This is printed-text OCR, not handwriting recognition.

## Editable objects

**Edit page objects** activates selection on the canvas. Click a visible text span or image, drag to move, or drag the lower-right handle to resize. Delete removes the selected object. Double-click or choose **Object properties** for exact X/Y/width/height, replacement text/image, and deletion. Invisible OCR text is excluded from the object selector.

Text replacements use Helvetica and preserve the original color, not the exact embedded font, styling or paragraph flow. Text must fit the specified width. Rotated text and overlapping spans are refused. Scan images cannot be edited as paragraphs; OCR makes their recognized text searchable, while the photographed characters remain part of the image. Editing that invisible OCR text does not visually rewrite the scan.

Direct PDF image placements can be moved, stretched, replaced and deleted without editing a shared image on other pages. Images inside complex drawing objects, repeated resources, or pages with inline image data are refused rather than changed ambiguously. This is an initial object editor, not Acrobat's full paragraph-layout engine.

## Scan cleanup and compression

**Review blank pages** scans the whole document for likely blank pages. Nothing is selected for deletion by default; inspect the candidates, check those to remove, then apply. Very faint markings can be missed.

**Clean selected scans** offers automatic straightening up to ±5 degrees, grayscale, contrast and resolution. It flattens selected pages into cleaned images and removes their old text layer. Run OCR afterward. Pages with forms, links or annotations are refused. Page objects and bookmark destinations are preserved; aggressive rotation can clip marks close to the edge.

**Compress to target size** exports a separate PDF. It tries lossless compression first, then increasingly smaller JPEG page renders with an approximate invisible text layer. It reports whether the target was reached and whether pages were rasterized. Documents containing forms, links or annotations use lossless compression only. Small targets are not guaranteed; inspect fine print, color and text selection afterward. The output does not exceed the source size.

## Reviewed search-and-redact

Enter a phrase, inspect the page/location list, uncheck occurrences you want to keep, and apply the checked redactions. Clicking a result previews its location. The exported PDF removes underlying text and covered image pixels. Save the redacted document as a new copy. Scans need OCR first; uncertain or missed OCR characters will not match a search, so also inspect them visually. Original documents, Undo snapshots and local backup versions remain available locally.

## Comparison

Choose another PDF. The app compares page positions, reports added/removed pages, shows a text diff, and detects rendered appearance changes including image-only differences. Select a result to view the pages side by side. Export the report as text.

This comparison does not intelligently align shifted or reordered pages, and it does not label which individual image caused an appearance change. It compares text and visible rendering, not every hidden metadata field or attachment. Unlock encrypted comparison files before choosing them.

## Organization

- **Bookmarks:** edit `level | title | physical page` lines, add the current page, or jump to the bookmark on the current line. Hierarchical internal bookmarks are supported; arbitrary external bookmark actions are not.
- **Page labels:** whole-document prefix and decimal/Roman/alphabetic labels. They are saved into the PDF; the app's page-number box still navigates by physical page number.
- **Headers, footers and numbering:** append text to selected pages, with a configurable first number. Existing content is not moved to make room, and repeated application appends another set. Use Undo to replace a newly added set.

## Validation

23 automated tests passed on Windows, including two real local OCR runs, invisible-text appearance preservation, OCR text-region extraction, image moves with a shared resource on another page, reviewed redaction selection, object replacement/deletion, blank detection, deskew, cleanup and bookmark preservation, compression/searchable text, visual-only comparison changes, and the native PDF dialogs. The final GUI suite uses Qt's offscreen platform and injected clipboard/dialog responses. Full real-desktop clipboard, printing and drag/drop testing remains separate.
