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
from typing import Any, Dict

try:
    # ftfy does a great job repairing mixed-encoding artefacts; keep optional.
    from ftfy import fix_text  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    fix_text = None


# Heuristics: characters/sequences that usually indicate bad decoding.
WEIRD_MARKERS = [
    "â", "Â", "ï", "آ", "�", "Ã", "أ،", "أ¢", "أ¯", "أ¤", "�",
    "â€", "â�", "â€™", "â€œ", "â€‌", "â€¢"
]
# Matches citation-like square-bracket notes such as:
# [12], [a], [N 1], [note 3], [nb 2], [n 4]
CITATION_RE = re.compile(
    r"\[\s*(?:[A-Za-z]{1,10}(?:\s+[A-Za-z]{1,10})*\s+)?\d+\s*\]"
    r"|\[\s*[A-Za-z]{1,4}\s*\]"
)
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")
CUSTOM_REPLACEMENTS: Dict[str, str] = {
    "آ°": "°",
    "â€²": "′",
    "â€³": "″",
    "â€“": "–",
    "â€”": "—",
    "â€¢": "•",
    "ï»؟": "",  # stray BOM sequence
    "أ،ت¼أ­": "Bahá’í",
}


DROP_KEYS = {
    "anthem",
    "motto",
    "demonyms",
    "president",
    "prime_minister",
    "speaker_of_the_parliament",
    "vice_president",
    "deputy_prime_minister",
    "king",
    "queen",
    "governor_general",
    "chancellor",
    "area_code",
    "calling_code",
    "postal_code",
    "internet_tld",
    "cctld",
    "iso_3166_code",
    "date_format",
    "time_zone",
    "currency",
    "currency_code",
    "patron_saint",
    "image_flag",
    "image_coat",
    "flag",
    "coat_of_arms",
    "locator_map",
    "map",
}

HISTORICAL_KEYWORDS = (
    "independ",
    "mandate",
    "kingdom",
    "sultanate",
    "emirate",
    "protectorate",
    "colony",
    "annex",
    "occupation",
    "established",
    "founded",
    "federation",
    "caliphate",
    "dynasty",
    "french_mandate",
    "ottoman",
    "roman",
    "byzantine",
)


def score_weird(text: str) -> int:
    """
    Heuristic cost: obvious mojibake markers plus replacement chars.
    Lower is better.
    """
    score = sum(text.count(ch) for ch in WEIRD_MARKERS)
    score += text.count("?")  # replacement characters from failed decodes
    return score


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
            # Use 'replace' to keep location info instead of silently dropping chars.
            candidate = text.encode(enc, errors="replace").decode("utf-8", errors="replace")
        except Exception:
            continue
        candidate_score = score_weird(candidate)
        if candidate_score < best_score:
            best, best_score = candidate, candidate_score

    return best


def clean_text(text: str) -> str:
    """Clean a single string field."""
    cleaned = demojibake(text)

    # Targeted fixes for frequent mojibake patterns.
    for bad, good in CUSTOM_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)

    # Remove zero-width marks and stray BOM strings.
    cleaned = ZERO_WIDTH_RE.sub("", cleaned)

    # Normalize Unicode and trim citations like "[12]", "[N 1]", "[note 3]".
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = CITATION_RE.sub("", cleaned)
    # Also drop short trailing bracket notes as a safety net.
    cleaned = re.sub(r"\s*\[\s*[^\]]{1,16}\s*\]\s*$", "", cleaned)

    # Simple punctuation fixes.
    cleaned = (
        cleaned.replace("â€¢", "•")
        .replace("•", "-")
        .replace("â€“", "–")
        .replace("â€”", "—")
        .replace("Â", "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )

    # Drop wrapping quotes when the entire field is quoted.
    # Example: '" Advance Australia Fair "' -> 'Advance Australia Fair'
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r'^\s*"\s*(.*?)\s*"\s*$', r"\1", cleaned)
        cleaned = re.sub(r"^\s*'\s*(.*?)\s*'\s*$", r"\1", cleaned)

    # Collapse whitespace.
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def canonicalize_key(key: str) -> str:
    value = clean_text(key)
    value = value.replace("(", " ").replace(")", " ")
    value = value.replace(":", " ").replace("/", " ")
    value = re.sub(r"\s+", " ", value).strip().lower()
    value = re.sub(r"\b(19|20)\d{2}\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_]+", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def should_drop_key(raw_key: str) -> bool:
    key = canonicalize_key(raw_key)
    if key in DROP_KEYS:
        return True
    return any(token in key for token in HISTORICAL_KEYWORDS)


def strip_coordinate_suffix(text: str) -> str:
    result = re.sub(r"\s+\d+[^/]*\/\s*\d+[^/]*\/\s*[\d.;\sNSEW°′″-]+$", "", str(text)).strip()
    return result or str(text).strip()


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

        cleaned = {}
        for k, v in value.items():
            key = clean_key(k)
            if should_drop_key(key):
                continue
            next_value = clean_value(v)
            if key.lower() in {"capital", "capital and largest city", "capital_and_largest_city", "largest city"}:
                if isinstance(next_value, str):
                    next_value = strip_coordinate_suffix(next_value)
                elif isinstance(next_value, list):
                    next_value = [
                        strip_coordinate_suffix(item) if isinstance(item, str) else item
                        for item in next_value
                    ]
            cleaned[key] = next_value
        return cleaned
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
