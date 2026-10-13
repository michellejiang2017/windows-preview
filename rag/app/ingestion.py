"""Read-only ingestion, reusing Preview's Document reader. No Qt or editor changes."""

import csv, hashlib, io, re, tempfile
from pathlib import Path
from dataclasses import dataclass
from desktop.engine import Document

MAX_BYTES = 5 * 1024 * 1024


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


def split(text, size=900, overlap=120):
    text = re.sub(r"[ \t]+", " ", text.replace("\r", "")).strip()
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(
                text.rfind("\n", start + size // 2, end),
                text.rfind(" ", start + size // 2, end),
            )
            if boundary > start:
                end = boundary
        value = text[start:end].strip()
        if value:
            yield value, start, end
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


def ingest(data, filename, source_url=""):
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ValueError("Files must be 5 MB or smaller.")
    filename = Path(filename.replace("\\", "/")).name[:150]
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".txt", ".csv"}:
        raise ValueError("Use a PDF, UTF-8 text, or CSV file.")
    digest = hashlib.sha256(data).hexdigest()
    units = []
    if extension == ".pdf":
        path = None
        reader = Document()
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as file:
                file.write(data)
                path = Path(file.name)
            reader.open([path])
            if reader.count > 150:
                raise ValueError("PDFs must have 150 pages or fewer.")
            for n, page in enumerate(reader.pdf):
                text = page.get_text(sort=True)
                if text.strip():
                    units.append(
                        (text, {"page": n + 1, "row": 0, "location": f"page {n+1}"})
                    )
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(
                "Could not read this PDF. Check that it is valid and not password-protected."
            ) from error
        finally:
            if reader.pdf is not None:
                reader.pdf.close()
            if path:
                path.unlink(missing_ok=True)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Text and CSV files must use UTF-8 encoding.") from error
        if extension == ".csv":
            table = csv.DictReader(io.StringIO(text))
            if not table.fieldnames or len(set(table.fieldnames)) != len(
                table.fieldnames
            ):
                raise ValueError("CSV needs a header with unique column names.")
            for n, row in enumerate(table, 1):
                if n > 500:
                    raise ValueError("CSV files must have 500 data rows or fewer.")
                if None in row:
                    raise ValueError("CSV row has more values than headers.")
                value = f"{filename}, data row {n}: " + "; ".join(
                    f'{k}: {v or ""}' for k, v in row.items()
                )
                if len(value) > 900:
                    raise ValueError("CSV rows must be shorter than 900 characters.")
                units.append(
                    (
                        value,
                        {
                            "page": 0,
                            "row": n,
                            "location": f"data row {n} (CSV line {n+1})",
                        },
                    )
                )
        else:
            units = [(text, {"page": 0, "row": 0, "location": "text passage"})]
    if sum(len(u[0]) for u in units) > 150000:
        raise ValueError("Document text exceeds the demo size limit.")
    chunks = []
    for unit, meta in units:
        for value, start, end in split(unit):
            metadata = {
                "filename": filename,
                "doc_id": digest,
                "source_url": source_url,
                "kind": extension[1:],
                "char_start": start,
                "char_end": end,
                **meta,
            }
            chunks.append(
                Chunk(f'{digest}:{meta["page"]}:{meta["row"]}:{start}', value, metadata)
            )
    if not chunks:
        raise ValueError(
            "No extractable text found. Scanned PDFs need OCR in Preview first."
        )
    if len(chunks) > 400:
        raise ValueError("Document produces too many passages for this demo.")
    return chunks
