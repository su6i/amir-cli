from typing import List


def rank_gemini_model_name(name: str) -> int:
    """Score Gemini model names for translation suitability."""
    score = 0
    name_lower = name.lower()

    if "3.0" in name_lower:
        score += 300
    elif "2.5" in name_lower:
        score += 250
    elif "2.0" in name_lower:
        score += 200
    elif "1.5" in name_lower:
        score += 150

    if "pro" in name_lower:
        score += 50
    elif "flash" in name_lower:
        score += 10

    if "exp" in name_lower:
        score -= 5
    if "preview" in name_lower:
        score -= 10
    if "thinking" in name_lower:
        score -= 15
    if "8b" in name_lower:
        score -= 20

    return score


def filter_gemini_generation_models(all_models) -> List[str]:
    """Filter non-text/specialized models and keep generateContent-capable models."""
    blacklist = ["image", "tts", "audio", "video", "voice", "embedding"]
    candidates = []
    for model in all_models:
        name_lower = model.name.lower()
        if any(word in name_lower for word in blacklist):
            continue
        actions = getattr(model, "supported_actions", []) or getattr(model, "supported_generation_methods", [])
        if "generateContent" in actions:
            candidates.append(model.name)
    return candidates
