import json
import re
from typing import Callable, List, Optional


def parse_translated_batch_output(
    output: str,
    expected_count: int,
    normalize_digits: Callable[[str], str],
    logger=None,
    threshold: float = 0.8,
) -> List[Optional[str]]:
    """Robustly parse model output into an ordered list of translated lines."""
    if not output:
        return []

    if "</think>" in output or "I'm capturing" in output or "I am capturing" in output:
        if logger is not None:
            logger.error("❌ LLM thinking detected in output! Model returned internal reasoning.")
        match = re.search(r'\{"1".*?\}', output, re.DOTALL)
        if match:
            try:
                parsed_json = json.loads(match.group())
                items = [str(parsed_json.get(str(i + 1), "")).strip() for i in range(expected_count)]
                if any(items):
                    if logger is not None:
                        logger.warning("⚠️ Salvaged translation from corrupted output")
                    return items
            except Exception:
                pass
        return []

    cleaned = output.strip()
    cleaned = re.sub(r"^```(?:json|text)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = normalize_digits(cleaned)

    if cleaned.startswith("[") or cleaned.startswith("{"):
        try:
            parsed_json = json.loads(cleaned)
            if isinstance(parsed_json, list):
                items = [str(item).strip() for item in parsed_json if str(item).strip()]
                if items:
                    return items[:expected_count]
            elif isinstance(parsed_json, dict):
                mapped = {}
                for k, v in parsed_json.items():
                    key_str = normalize_digits(str(k).strip())
                    if key_str.isdigit():
                        mapped[int(key_str)] = str(v).strip()
                if mapped:
                    ordered = [mapped.get(i) for i in range(1, expected_count + 1)]
                    valid_count = sum(1 for v in ordered if v is not None)
                    if expected_count == 0 or valid_count >= int(expected_count * threshold):
                        return ordered
        except Exception:
            pass

    parsed_lines = {}
    current_num = None
    for raw_line in cleaned.split("\n"):
        line = normalize_digits(raw_line.strip())
        if not line:
            continue

        match = re.match(r"^[\-\*•\u2022]?\s*[\(\[]?(\d+)[\)\]\.\-:\s]+(.*)", line)
        if match:
            num = int(match.group(1))
            content = match.group(2).strip().strip('"').strip("'")
            parsed_lines[num] = content if content else parsed_lines.get(num, "")
            current_num = num
            continue

        if current_num is not None:
            prev = parsed_lines.get(current_num, "")
            parsed_lines[current_num] = f"{prev} {line}".strip()

    ordered: List[Optional[str]] = []
    for i in range(1, expected_count + 1):
        value = parsed_lines.get(i)
        ordered.append(value if value else None)

    valid_count = sum(1 for v in ordered if v and v.strip())
    if expected_count == 0 or valid_count >= int(expected_count * threshold):
        return ordered

    return []
