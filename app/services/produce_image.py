"""Map a listing name to a Satokori woodcut. Specific names beat category fallbacks."""

from __future__ import annotations

# Longer / more specific keys first.
_NAME_RULES: list[tuple[tuple[str, ...], str]] = [
    (("ostrich", "strutsi"), "ostrich-egg.jpg"),
    (("lehtikaali", "kale"), "greens.jpg"),
    (("raspberry", "raspberr", "vadelma"), "raspberry.jpg"),
    (("blueberry", "blueberr", "mustikka"), "blueberry.jpg"),
    (("strawberry", "strawberr", "mansikka"), "strawberry.jpg"),
    (("tyrni", "sea buckthorn"), "tyrni.jpg"),
    (("haskap", "hunajamarja"), "blueberry.jpg"),
    (("cabbage", "kerakaali", "kaali"), "cabbage.jpg"),
    (("lettuce", "salaatti", "chard", "mangold", "vegetable", "vegetables"), "lettuce.jpg"),
    (("honey", "hunaja"), "honey.jpg"),
    (("juice", "mehu"), "juice.jpg"),
    (("yarn", "wool", "alpaca", "lanka"), "yarn.jpg"),
    (("oat", "kaura", "flake", "hiutale"), "oats.jpg"),
    (("flour", "jauho"), "oats.jpg"),
]

_CAT_FILES = {
    "dairy": "dairy.jpg",
    "eggs": "eggs.jpg",
    "greens": "greens.jpg",
    "berries": "berries.jpg",
    "root": "root.jpg",
    "preserve": "preserve.jpg",
    "feed": "feed.jpg",
    "produce": "produce.jpg",
    "meat": "meat.jpg",
}

_MEAT_WORDS = ("beef", "lamb", "meat", "liha", "karitsa", "nauta", "poro")


def _norm_category(cat: str | None, name: str = "") -> str:
    c = (cat or "produce").lower()
    if c in ("vegetable", "vegetables"):
        c = "greens"
    n = (name or "").lower()
    if any(w in n for w in _MEAT_WORDS):
        c = "meat"
    if c not in _CAT_FILES:
        c = "produce"
    return c


def produce_image_file(name: str | None, category: str | None = None) -> str:
    n = (name or "").lower()
    for keys, filename in _NAME_RULES:
        if any(k in n for k in keys):
            return filename
    cat = _norm_category(category, name or "")
    return _CAT_FILES.get(cat, "produce.jpg")


# Bump when the pack is recompressed so browsers drop the old 1024px files.
PRODUCE_IMAGE_V = "2"


def produce_image_url(name: str | None, category: str | None = None) -> str:
    return f"/static/produce/{produce_image_file(name, category)}?v={PRODUCE_IMAGE_V}"
