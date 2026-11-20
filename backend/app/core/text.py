import re
import unicodedata


def slugify(value: str) -> str:
    """'Cerámica para principiantes' -> 'ceramica-para-principiantes' (URLs SEO)."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:120] or "curso"
