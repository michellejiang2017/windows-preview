# PDF-focused v3 verification

Executed on Windows x64 with Python 3.12, October 10, 2026.

**30 automated tests passed.** Command: `python -m pytest test_preview.py test_pdf_tools.py test_usability.py -q`.

Covered PDF/image merging, page extraction/reorder/delete/duplicate, original preservation, undo/redo, text and image-stream redaction, selective match redaction, encryption, metadata/annotation/link removal, forms, image exports, GPS and alpha tools, native Qt actions/navigation/multiselect/crop/paste, local versions and view-only dark mode.

New checks cover two real local OCR runs, searchable and selectable invisible text, unchanged scan appearance, skipping existing text, object text/image move/replace/delete, preservation of shared resources on other pages, refusal of complex/repeated image placements, PDF operator parsing, blank detection, synthetic deskew, scan cleanup and bookmark destination preservation, form-page refusal, target compression/searchable text, text and image-only comparison changes, bookmarks/labels/numbering and native PDF dialog wiring.

GUI tests use Qt offscreen rendering, an injected clipboard and automated dialog responses. The original prototype also passed a visible-window smoke run. Full desktop clipboard, shell drag/drop, hardware printing, large or unusual documents and exhaustive codecs remain unverified. OCR quality varies. Limitations are detailed in PDF-TOOLS.md.

The previous image-cutout smoke test passed using U2NetP. No additional 3D work was performed.

The usability checks cover highlighted text selection and clipboard copying, actual Qt mouse dragging of an image, move/resize/delete/undo, Ctrl+S without a Save As dialog, extension completion, PDF/image drop events and password preservation when overwriting an encrypted PDF. The Preview-inspired window was rendered and visually inspected. Explorer-to-app shell drag/drop is still not independently verified.
