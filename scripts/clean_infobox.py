"""
Clean the infobox JSON files by fixing mojibake, stripping citation brackets,
and normalizing whitespace. Writes cleaned copies to a destination folder so
the raw data stays untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


try:
    # ftfy does a great job repairing mixed-encoding artefacts; keep optional.
    from ftfy import fix_text  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    fix_text = None


WEIRD_CHARS = ["â", "Â", "ï", "آ", "�"]
# Matches footnote markers like "[ 12 ]" or "[ a ]".
CITATION_RE = re.compile(r"\[\s*[0-9a-zA-Z]+\s*\]")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")


def score_weird(text: str) -> int:
    """Count obvious mojibake markers."""
    return sum(text.count(ch) for ch in WEIRD_CHARS)


def demojibake(text: str) -> str:
    """
    Try a couple of common re-decodings that fix UTF-8 read as Windows-125x.
    Pick the variant that reduces obvious garbage characters.
    """
    best = text
    best_score = score_weird(text)

    # Optional high-quality fix.
    if fix_text:
        candidate = fix_text(text)
        candidate_score = score_weird(candidate)
        if candidate_score < best_score:
            best, best_score = candidate, candidate_score

    for enc in ("cp1256", "cp1252", "latin1"):
        try:
            candidate = text.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            continue
        candidate_score = score_weird(candidate)
        if candidate_score < best_score:
            best, best_score = candidate, candidate_score

    return best


def clean_text(text: str) -> str:
    """Clean a single string field."""
    cleaned = demojibake(text)

    # Remove zero-width marks and stray BOM strings.
    cleaned = ZERO_WIDTH_RE.sub("", cleaned).replace("ï»؟", "")

    # Normalize Unicode and trim citations like "[ 12 ]".
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = CITATION_RE.sub("", cleaned)

    # Simple punctuation fixes.
    cleaned = (
        cleaned.replace("â€¢", "•")
        .replace("•", "-")
        .replace("â€“", "–")
        .replace("â€”", "—")
        .replace("Â", "")
    )

    # Collapse whitespace.
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def clean_value(value: Any) -> Any:
    """Recursively clean strings in nested dict/list structures."""
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [clean_value(v) for v in value]
    if isinstance(value, dict):
        def clean_key(k: str) -> str:
            base = clean_text(k)
            # Drop leading bullets/dashes used as list markers.
            return re.sub(r"^[•\-–—]\s*", "", base)

        return {clean_key(k): clean_value(v) for k, v in value.items()}
    return value


def process_file(src_path: Path, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(src_path.read_text(encoding="utf-8"))
    cleaned = clean_value(data)
    dst_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean infobox JSON files.")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("data/infobox_json"),
        help="Folder containing raw infobox JSON files.",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        default=Path("data/infobox_json_clean"),
        help="Where to write cleaned JSON files.",
    )
    args = parser.parse_args()

    for path in sorted(args.src.glob("*.json")):
        rel = path.name
        process_file(path, args.dst / rel)


if __name__ == "__main__":
    main()
