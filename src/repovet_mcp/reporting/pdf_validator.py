"""Structural PDF validation and parsing utility for verifying generated reports."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PDFValidationResult:
    """Structured result of PDF structural validation."""

    is_valid: bool
    version: str = "unknown"
    page_count: int = 0
    object_count: int = 0
    file_size_bytes: int = 0
    has_magic_header: bool = False
    has_eof_marker: bool = False
    has_catalog: bool = False
    has_pages_tree: bool = False
    errors: list[str] = field(default_factory=list)


class PDFStructuralValidator:
    """Validates structural integrity, object hierarchy, and page trees of PDF files."""

    OBJ_REGEX = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")
    PAGE_REGEX = re.compile(rb"/Type\s*/Page\b")
    CATALOG_REGEX = re.compile(rb"/Type\s*/Catalog\b")
    PAGES_TREE_REGEX = re.compile(rb"/Type\s*/Pages\b")
    COUNT_REGEX = re.compile(rb"/Count\s+(\d+)\b")
    MEDIABOX_REGEX = re.compile(rb"/MediaBox\s*\[\s*([\d\.\s]+)\s*\]")

    def validate_file(self, pdf_path: Path | str) -> PDFValidationResult:
        """Read and structurally validate a PDF file on disk."""
        path = Path(pdf_path)
        if not path.exists():
            return PDFValidationResult(
                is_valid=False,
                errors=[f"PDF file does not exist: {path}"],
            )

        content = path.read_bytes()
        return self.validate_bytes(content)

    def validate_bytes(self, content: bytes) -> PDFValidationResult:
        """Parse and validate raw PDF byte content."""
        errors: list[str] = []
        file_size = len(content)

        if file_size < 100:
            return PDFValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                errors=["PDF content too small to be a valid document (< 100 bytes)."],
            )

        # 1. Check Magic Header (%PDF-X.Y)
        has_magic = content.startswith(b"%PDF-")
        version = "unknown"
        if has_magic:
            first_line = content[:30].split(b"\n")[0].decode("ascii", errors="replace")
            match = re.match(r"%PDF-(\d+\.\d+)", first_line)
            if match:
                version = match.group(1)
            else:
                errors.append("Invalid PDF version header format.")
        else:
            errors.append("Missing %PDF- magic header at byte 0.")

        # 2. Check End of File Marker (%%EOF)
        tail_window = content[-256:]
        has_eof = b"%%EOF" in tail_window
        if not has_eof:
            errors.append("Missing %%EOF end-of-file trailer marker within last 256 bytes.")

        # 3. Check Cross-Reference / startxref Table
        has_startxref = b"startxref" in tail_window or b"startxref" in content[-1024:]
        if not has_startxref:
            errors.append("Missing 'startxref' cross-reference table pointer.")

        # 4. Count Defined Objects
        objs = self.OBJ_REGEX.findall(content)
        object_count = len(objs)
        if object_count == 0:
            errors.append("No valid PDF objects ('N M obj') detected.")

        # 5. Check Catalog Root Object
        has_catalog = bool(self.CATALOG_REGEX.search(content))
        if not has_catalog:
            errors.append("Missing Root Catalog dictionary ('/Type /Catalog').")

        # 6. Check Pages Tree and Page Count
        has_pages_tree = bool(self.PAGES_TREE_REGEX.search(content))
        if not has_pages_tree:
            errors.append("Missing Pages tree dictionary ('/Type /Pages').")

        # Page count from /Type /Page occurrences
        individual_pages = self.PAGE_REGEX.findall(content)
        observed_pages = len(individual_pages)

        # Check declared /Count in /Type /Pages
        count_match = self.COUNT_REGEX.search(content)
        declared_count = int(count_match.group(1)) if count_match else observed_pages

        final_page_count = max(observed_pages, declared_count)
        if final_page_count == 0:
            errors.append("Document contains 0 renderable pages.")

        # 7. Check MediaBox Dimensions on Pages
        mediaboxes = self.MEDIABOX_REGEX.findall(content)
        if observed_pages > 0 and len(mediaboxes) == 0:
            errors.append("No MediaBox boundary boxes defined for pages.")

        is_valid = len(errors) == 0

        return PDFValidationResult(
            is_valid=is_valid,
            version=version,
            page_count=final_page_count,
            object_count=object_count,
            file_size_bytes=file_size,
            has_magic_header=has_magic,
            has_eof_marker=has_eof,
            has_catalog=has_catalog,
            has_pages_tree=has_pages_tree,
            errors=errors,
        )
