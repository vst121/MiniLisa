"""
PDF Document Parser Module.
Combines PyMuPDF (fitz) for fast text & metadata extraction with pdfplumber for structured table extraction.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    raw_text: str
    page_count: int
    tables: list[list[list[str | None]]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """PDF Parsing service utilizing PyMuPDF and pdfplumber."""

    @staticmethod
    def parse_pdf(file_path: str | Path) -> ExtractedDocument:
        """Parse PDF document and return raw text, page metadata, and extracted tables."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at path: {file_path}")

        logger.info(f"[DocumentParser] Parsing PDF document: {path.name}")

        # 1. PyMuPDF fast text extraction
        full_text_pages: list[str] = []
        page_count = 0
        doc_metadata: dict[str, Any] = {}

        try:
            doc = fitz.open(str(path))
            page_count = len(doc)
            doc_metadata = {
                "format": doc.metadata.get("format"),
                "title": doc.metadata.get("title"),
                "author": doc.metadata.get("author"),
                "page_count": page_count,
            }
            for page in doc:
                text = page.get_text("text")
                full_text_pages.append(text)
            doc.close()
        except Exception as e:
            logger.error(f"[DocumentParser] PyMuPDF parsing failed: {e}")
            full_text_pages = [f"Failed to read PDF text: {e}"]

        raw_text = "\n--- PAGE BREAK ---\n".join(full_text_pages)

        # 2. pdfplumber structured table extraction
        extracted_tables: list[list[list[str | None]]] = []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            extracted_tables.append(table)
        except Exception as e:
            logger.warning(f"[DocumentParser] pdfplumber table extraction warning: {e}")

        logger.info(
            f"[DocumentParser] Extracted {page_count} pages, {len(raw_text)} chars, {len(extracted_tables)} tables."
        )

        return ExtractedDocument(
            raw_text=raw_text,
            page_count=page_count,
            tables=extracted_tables,
            metadata=doc_metadata,
        )
