"""Tests for interviewd.planner.ingestion — text extraction from files."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from interviewd.planner.ingestion import extract_text


# ---------------------------------------------------------------------------
# Plain text / markdown
# ---------------------------------------------------------------------------


def test_extract_txt(tmp_path):
    f = tmp_path / "jd.txt"
    f.write_text("Software Engineer at Acme Corp.", encoding="utf-8")
    assert extract_text(str(f)) == "Software Engineer at Acme Corp."


def test_extract_md(tmp_path):
    f = tmp_path / "resume.md"
    f.write_text("# John Doe\n\n5 years Python.", encoding="utf-8")
    assert "John Doe" in extract_text(str(f))


def test_extract_txt_preserves_unicode(tmp_path):
    f = tmp_path / "jd.txt"
    f.write_text("Résumé: café ☕", encoding="utf-8")
    assert "Résumé" in extract_text(str(f))


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_extract_missing_file_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        extract_text("/nonexistent/path/jd.txt")


def test_extract_unsupported_extension_raises(tmp_path):
    f = tmp_path / "doc.docx"
    f.write_bytes(b"binary content")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(str(f))


# ---------------------------------------------------------------------------
# PDF — ImportError path (pypdf not installed)
# ---------------------------------------------------------------------------


def test_extract_pdf_without_pypdf_raises_import_error(tmp_path):
    """If pypdf is absent the caller gets a clear install instruction."""
    f = tmp_path / "jd.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    # Temporarily hide pypdf from the import system
    with patch.dict(sys.modules, {"pypdf": None}):
        with pytest.raises(ImportError, match="uv pip install interviewd\\[planner\\]"):
            extract_text(str(f))


# ---------------------------------------------------------------------------
# PDF — happy path (pypdf mocked)
# ---------------------------------------------------------------------------


def test_extract_pdf_happy_path(tmp_path):
    f = tmp_path / "jd.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Senior Python Engineer"

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    mock_pypdf = MagicMock()
    mock_pypdf.PdfReader.return_value = mock_reader

    with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
        # Re-import so the patched sys.modules is used inside _extract_pdf
        import importlib
        import interviewd.planner.ingestion as mod
        importlib.reload(mod)
        result = mod.extract_text(str(f))

    assert result == "Senior Python Engineer"
