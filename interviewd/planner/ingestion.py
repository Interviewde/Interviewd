"""Text extraction from JD / resume files.

Supports plain text (.txt, .md) out of the box.
PDF support requires the optional ``planner`` extra::

    uv pip install interviewd[planner]
"""

from pathlib import Path


def extract_text(path: str) -> str:
    """Return the plain-text content of a file.

    Args:
        path: Path to a ``.pdf``, ``.txt``, or ``.md`` file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
        ImportError: If a PDF is provided but ``pypdf`` is not installed.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(p)
    if suffix in (".txt", ".md"):
        return p.read_text(encoding="utf-8")
    raise ValueError(
        f"Unsupported file type '{suffix}'. Provide a .pdf, .txt, or .md file."
    )


def _extract_pdf(path: Path) -> str:
    try:
        import pypdf  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "PDF ingestion requires pypdf. Install it with:\n"
            "  uv pip install interviewd[planner]"
        ) from exc

    reader = pypdf.PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)
