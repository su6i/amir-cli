import re


def fix_persian_text(text: str) -> str:
    if not text:
        return text

    text = re.sub(r"\s+([\.!؟،؛])", r"\1", text)

    informal = {
        r"\bمی‌باشند\b": "هستن",
        r"\bمی‌باشد\b": "هست",
    }
    for p, r in informal.items():
        text = re.sub(p, r, text)

    zwnj_patterns = [
        # Plural suffix with space: "کتاب ها" -> "کتاب‌ها"
        (r"([\u0600-\u06FF]+)(\s+)(ها)(\s|$)", "\\1\u200c\\3\\4"),

        # Verb prefix joins (spaced): "می رود" / "نمی دانم"
        (r"\b(ن?می)\s+([\u0600-\u06FF])", "\\1\u200c\\2"),

        # Compounds with space: "کوچک کننده" / "تبعیض آمیز"
        (r"([\u0600-\u06FF]+)\s+(کننده|کنندگان|کنندگی)\b", "\\1\u200c\\2"),
        (r"([\u0600-\u06FF]+)\s+(آمیز)\b", "\\1\u200c\\2"),
        # Compounds stuck without space: "کوچککننده" / "تبعیضآمیز"
        (r"([\u0600-\u06FF]{2,})(کننده|کنندگان|کنندگی)\b", "\\1\u200c\\2"),
        (r"([\u0600-\u06FF]{2,})(آمیز)\b", "\\1\u200c\\2"),
    ]
    for pat, repl in zwnj_patterns:
        text = re.sub(pat, repl, text)

    for _cp in (
        "\u200f",
        "\u200e",
        "\u200d",
        "\u202b",
        "\u202a",
        "\u202c",
        "\u202e",
        "\u202d",
        "\u2067",
        "\u2066",
        "\u2069",
    ):
        text = text.replace(_cp, "")

    text = text.strip()
    text = re.sub(r"^([.!:،؛؟]+)(.+)$", r"\2\1", text)

    _LRI = "\u2066"
    _PDI = "\u2069"
    _RLI = "\u2067"
    text = re.sub(r"(\([A-Za-z][^)]*\))", _LRI + r"\1" + _PDI, text)
    text = _RLI + text + _PDI
    return text


def strip_english_echo(text: str) -> str:
    """Strip echoed English prefix from a Persian translation."""
    if not text:
        return text

    persian_start = -1
    for i, c in enumerate(text):
        if "\u0600" <= c <= "\u06FF":
            persian_start = i
            break

    if persian_start < 0:
        return text
    if persian_start == 0:
        return text

    prefix = text[:persian_start]
    if re.search(r"[a-zA-Z]{2,}", prefix):
        return text[persian_start:].strip()
    return text


def clean_bidi(t: str) -> str:
    """Strip BiDi directional control chars. Preserves ZWNJ (\u200C)."""
    if not t:
        return ""
    for cp in (
        "\u200f",
        "\u200e",
        "\u200d",
        "\u202b",
        "\u202a",
        "\u202c",
        "\u202e",
        "\u202d",
    ):
        t = t.replace(cp, "")
    return t.strip()
