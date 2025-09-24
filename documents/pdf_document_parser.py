import argparse
import json
import sys
from pathlib import Path

import pdfplumber

DEFAULT_PDF_PATH = r"C:\Users\Bhuwan\Downloads\Research on the CSR tools based on Gen AI for government uses.pdf"

def extract_pdf_text(pdf_path: Path) -> dict:
    """
    Extract text from a PDF using pdfplumber and return a JSON-serializable dict.

    Structure:
    {
        "file": str,
        "num_pages": int,
        "pages": [
            {"page_number": int, "text": str},
            ...
        ],
        "full_text": str,
    }
    """
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []
    full_text_parts = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            # Extract text; fall back to empty string if None
            text = page.extract_text(x_tolerance=1, y_tolerance=1) or ""
            pages.append({"page_number": idx, "text": text})
            full_text_parts.append(text)

    full_text = "\n\n".join(full_text_parts)

    return {
        "file": str(pdf_path),
        "num_pages": len(pages),
        "pages": pages,
        "full_text": full_text,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse a PDF and emit extracted text as JSON using pdfplumber.",
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        default=DEFAULT_PDF_PATH,
        help=f"Path to the input PDF file (default: {DEFAULT_PDF_PATH})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write JSON output. If omitted, prints to stdout.",
    )

    args = parser.parse_args(argv)

    pdf_path = Path(args.input)

    try:
        result = extract_pdf_text(pdf_path)
        json_output = json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error surface
        # Emit machine-readable error JSON to stderr
        error_obj = {"error": str(exc), "file": str(pdf_path)}
        print(json.dumps(error_obj, ensure_ascii=False), file=sys.stderr)
        return 1

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output, encoding="utf-8")
    else:
        # Print to stdout
        print(json_output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


