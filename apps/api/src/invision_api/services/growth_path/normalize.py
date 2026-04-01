"""Whitespace normalization for growth answers (shared with payload validation)."""


def normalize_growth_text(raw: str) -> str:
    """Trim and collapse internal whitespace to single spaces."""
    return " ".join(raw.split()).strip()
