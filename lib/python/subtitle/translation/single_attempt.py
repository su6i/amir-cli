import time
from typing import List

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def translate_batch_single_attempt(
    processor,
    batch: List[str],
    target_lang: str,
    source_lang: str = "en",
    model_name: str = "deepseek",
    batch_size: int = 25,
    max_retries: int = 2,
    has_gemini: bool = False,
) -> List[str]:
    """Run one model translation flow with limited retries and strict output size."""

    if model_name == "deepseek":
        if not HAS_OPENAI:
            raise ImportError("OpenAI package required for DeepSeek translation. Please install with 'pip install openai'")
        client = OpenAI(api_key=processor.api_key, base_url="https://api.deepseek.com/v1")

        for attempt in range(1, max_retries + 1):
            try:
                batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])

                response = client.chat.completions.create(
                    model=processor.llm_models["deepseek"],
                    messages=[
                        {"role": "system", "content": processor.get_translation_prompt(target_lang)},
                        {"role": "user", "content": batch_text},
                    ],
                    temperature=processor.temperature,
                    max_tokens=4000,
                )

                output = response.choices[0].message.content.strip()

                if hasattr(response, "usage") and response.usage:
                    cached_tokens = getattr(response.usage, "prompt_cache_hit_tokens", 0) or 0
                    if cached_tokens:
                        processor._cost_savings["deepseek_cache_hit_tokens"] += cached_tokens

                trans_list = processor._parse_translated_batch_output(output, len(batch))

                if trans_list and len(trans_list) >= len(batch):
                    if target_lang == "fa":
                        processed_list = []
                        for idx_in_batch, t in enumerate(trans_list):
                            if not t or not t.strip():
                                processed_list.append(batch[idx_in_batch])
                                continue
                            if not any("\u0600" <= c <= "\u06FF" for c in t):
                                processed_list.append(batch[idx_in_batch])
                            else:
                                processed_list.append(processor.fix_persian_text(processor.strip_english_echo(t)))
                        trans_list = processed_list
                    return trans_list[: len(batch)]
                raise ValueError(
                    f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}"
                )

            except Exception as e:
                if attempt >= max_retries:
                    raise
                wait_time = 5 * attempt
                processor.logger.debug(
                    f"DeepSeek attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}"
                )
                time.sleep(wait_time)

    elif model_name == "minimax":
        for attempt in range(1, max_retries + 1):
            try:
                import requests

                api_key = processor.minimax_api_key
                if not api_key:
                    raise ValueError("MINIMAX_API_KEY not set")

                batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])

                headers = {"Authorization": f"Bearer {api_key}"}
                data = {
                    "model": processor.llm_models["minimax"],
                    "messages": [
                        {"role": "system", "content": processor.get_translation_prompt(target_lang)},
                        {"role": "user", "content": batch_text},
                    ],
                }

                response = requests.post(
                    "https://api.minimaxi.com/v1/text/chatcompletion_pro",
                    json=data,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                output = result.get("reply", "")
                trans_list = processor._parse_translated_batch_output(output, len(batch))

                if trans_list and len(trans_list) >= len(batch):
                    return trans_list[: len(batch)]
                raise ValueError(
                    f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}"
                )

            except Exception as e:
                if attempt >= max_retries:
                    raise
                wait_time = 5 * attempt
                processor.logger.debug(
                    f"MiniMax attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}"
                )
                time.sleep(wait_time)

    elif model_name == "gemini":
        gemini_cache_name = processor._get_gemini_content_cache(target_lang)

        for attempt in range(1, max_retries + 1):
            try:
                if not has_gemini or not processor.google_api_key:
                    raise ValueError("Gemini SDK not available or API key not set")

                from google import genai
                from google.genai import types as genai_types

                client = genai.Client(api_key=processor.google_api_key)

                batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
                model = processor.llm_models["gemini"]

                if gemini_cache_name:
                    response = client.models.generate_content(
                        model=model,
                        contents=batch_text,
                        config=genai_types.GenerateContentConfig(cached_content=gemini_cache_name),
                    )
                else:
                    response = client.models.generate_content(
                        model=model,
                        contents=f"{processor.get_translation_prompt(target_lang)}\n\n{batch_text}",
                    )

                output = response.text.strip() if response else ""
                if not output:
                    raise ValueError(f"Empty response from {model}")

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    cached = getattr(response.usage_metadata, "cached_content_token_count", 0) or 0
                    if cached:
                        processor._cost_savings["gemini_cached_tokens"] += cached

                trans_list = processor._parse_translated_batch_output(output, len(batch))
                if trans_list and len(trans_list) >= len(batch):
                    return trans_list[: len(batch)]
                raise ValueError(
                    f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}"
                )

            except Exception as e:
                if attempt >= max_retries:
                    raise
                wait_time = 5 * attempt
                processor.logger.debug(
                    f"Gemini attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}"
                )
                time.sleep(wait_time)

    elif model_name == "grok":
        for attempt in range(1, max_retries + 1):
            try:
                from openai import OpenAI as XAI_Client

                if not processor.grok_api_key:
                    raise ValueError("GROK_API_KEY not set")

                client = XAI_Client(api_key=processor.grok_api_key, base_url="https://api.x.ai/v1")
                batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])

                response = client.chat.completions.create(
                    model=processor.llm_models["grok"],
                    messages=[
                        {"role": "system", "content": processor.get_translation_prompt(target_lang)},
                        {"role": "user", "content": batch_text},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )

                output = (response.choices[0].message.content or "").strip()
                if not output:
                    raise ValueError("Empty response from Grok")

                if hasattr(response, "usage") and response.usage:
                    cached_tokens = getattr(response.usage, "prompt_cache_hit_tokens", 0) or 0
                    if cached_tokens:
                        processor._cost_savings["grok_cache_hit_tokens"] += cached_tokens

                trans_list = processor._parse_translated_batch_output(output, len(batch))
                if trans_list and len(trans_list) >= len(batch):
                    return trans_list[: len(batch)]
                raise ValueError(
                    f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}"
                )

            except Exception as e:
                if attempt >= max_retries:
                    raise
                wait_time = 5 * attempt
                processor.logger.debug(
                    f"Grok attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}"
                )
                time.sleep(wait_time)

    else:
        raise ValueError(f"Unknown model: {model_name}")

    raise ValueError(f"Unknown model: {model_name}")