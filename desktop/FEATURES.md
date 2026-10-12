# Video feature requirements and implementation

## PDF-focused v2 update

The current build adds all six requested PDF tool groups: local OCR, object editing, scan cleanup/compression, reviewed search-and-redact, document comparison, and bookmarks/labels/headers/footers/numbering. See PDF-TOOLS.md for operation details and limitations. At the user's request, 3D is excluded from the current interface and default dependencies. The video matrix below records the original prototype mapping; its 3D entry is historical, not current functionality.

Confirmed app: **Apple Preview on macOS**, presented by MacVince. Source is the supplied video's own chapter list and English transcript. “Adapted” means a Windows substitute; “partial” explicitly denotes a fidelity gap.

| Video | Requirement | Windows implementation |
|---|---|---|
| 0:00 | Thumbnails and page reorder | Native thumbnail list; drag reorder; Ctrl/Shift multiselect |
| 0:42 | Extract pages to new PDF | Export selected pages / Ctrl+E; direct drag-out is not implemented |
| 0:53 | Merge PDFs | Insert PDFs; window file-drop; selected-page export then insert |
| 1:01 | Images become PDF pages | Insert images directly; image sessions export to PDF |
| 1:08 | Contact sheet | Thumbnail grid overview and printable PDF sheet |
| 1:19 | Drag document for attachment | Drag file button for saved files |
| 1:33 | True text/image redaction | Applied MuPDF redactions, full rewrite with garbage collection |
| 2:05 | One-click background removal | Local U2NetP segmentation; first-use model download |
| 2:11 | Manual color alpha selection | Click a color with adjustable tolerance; applies across image |
| 2:23 | Copy subject | Segmentation output copied with transparency |
| 2:30 | New from clipboard | Ctrl+Shift+N |
| 2:37 | Collages and image rotation | Paste-and-place compositing; arbitrary rotation dialog; no trackpad twist |
| 2:50 | Paste image on PDF | Direct image insertion on page; no macOS workaround required |
| 3:20 | Image resize and estimate | Pixels/percent, aspect preserved, PNG size estimate |
| 3:38 | Photo adjustments | Exposure, contrast, saturation, sharpness; batch selected images |
| 3:53 | Revert historical document edits | In-session undo/redo; previous overwritten files backed up locally |
| 4:12 | PDF metadata inspector | Document properties, all annotation info, links |
| 4:27 | Embedded AI editing info | Shows available image metadata; no C2PA verification or AI classifier |
| 4:34 | GPS metadata | EXIF GPS data in Inspector |
| 4:40 | Remove location | Remove GPS; strip all metadata; export without EXIF |
| 4:52 | Batch-delete annotations and links | Separate whole-document removal actions |
| 5:07 | Annotation author preference | Persistent name; anonymous by default; strip existing names |
| 5:23 | Edit/view/render 3D | Partial: mesh transforms, cameras, lighting, PNG; no photorealism, materials, per-object edit or model export |
| 5:41 | Broad file imports | Common raster codecs, HEIF/AVIF, PSD composite, PDF, mesh formats; no exhaustive macOS format parity |
| 5:54 | Files onto dock icon | Adapted: drop on window or launcher; command-line file arguments |
| 6:02 | Folders onto dock icon | Adapted: drop folder or Open folder; immediate images grouped |
| 6:11 | Batch convert/resize/rotate | Selected-image batch tools and exports |
| 6:17 | Hidden export formats | Additional codec formats always visible; no Option-key hiding |
| 6:35 | Customize toolbar | Persistently show/hide document toolbar actions |
| 6:48 | Page flicker and force-press speed | Hold-to-repeat arrow buttons; no pressure-sensitive acceleration |
| 6:59 | Navigation back/forward | Internal PDF links and page navigation history |
| 7:09 | Page number box | Direct native page-number input |
| 7:14 | Canvas color | Persistent background color picker |
| 7:24 | Dark PDF appearance | View-only color inversion; exports unchanged |
| 7:40 | Apple Notes inline PDFs | Adapted: ordinary file drag to compatible Windows notes apps; no Apple Notes integration |

## Added beyond the video

Blank PDF creation; blank-page insertion; deletion and duplication; page replacement; page crop; rectangle/highlight/pen/text marks; editable PDF form fields; extraction of text and embedded image streams; per-page image rendering; encrypted PDF export and print/copy flags; native printing; metadata clearing; undo/redo; image painting/crop; explicit supported-format errors.

## Remaining work for full parity

1. 3D parity is outside the current requested scope.
2. Drag selected pages directly to Explorer and between app windows; thumbnail-target insertion position.
3. Additional professional/RAW formats, C2PA signature verification and fuller photo controls.
4. Windows notes integration, advanced touch gestures, pressure-sensitive page flicker and OS history integration.
5. Production hardening: very large document performance, finer annotation management, asynchronous rendering, installers/signing, accessibility review and broader file compatibility tests.

Those features are not presented as completed. Apple's proprietary OS integrations do not have direct portable equivalents.
