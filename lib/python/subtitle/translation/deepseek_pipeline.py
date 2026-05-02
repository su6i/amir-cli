import time
from typing import Dict, List, Optional

from openai import OpenAI
from tqdm import tqdm

from subtitle.config import has_target_language_chars

from .deepseek_helpers import build_contextual_batch_text, write_partial_translation_srt


def run_deepseek_translation_pipeline(
    processor,
    texts: List[str],
    target_lang: str,
    source_lang: str = 'en',
    batch_size: int = 25,
    original_entries: Optional[List[Dict]] = None,
    output_srt: Optional[str] = None,
    existing_translations: Optional[Dict[int, str]] = None,
    has_gemini: bool = False,
) -> List[str]:
    """DeepSeek-first translation pipeline with per-batch Gemini fallback."""
    if not texts or target_lang == source_lang:
        return texts

    indices = list(range(len(texts)))
    client = OpenAI(api_key=processor.api_key, base_url='https://api.deepseek.com/v1')

    final_result = [None] * len(texts)
    if existing_translations:
        for idx, txt in existing_translations.items():
            if 0 <= idx < len(final_result) and txt and txt.strip():
                final_result[idx] = txt

    indices_to_translate = [i for i in indices if final_result[i] is None]
    if not indices_to_translate:
        return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

    batch_indices_list = processor._create_balanced_batches(indices_to_translate, texts, batch_size)
    batch_count = len(batch_indices_list)
    pbar = tqdm(total=len(indices), unit='item', desc=f'  Translating ({target_lang.upper()})')

    for i, batch_indices in enumerate(batch_indices_list):
        batch = [texts[idx] for idx in batch_indices]
        pbar.set_postfix({'batch': f'{i + 1}/{batch_count}'})

        current_target_indices = list(batch_indices)
        attempt = 0
        max_retries = 10
        success_batch = False
        last_error_msg = ''

        while attempt < max_retries and current_target_indices:
            attempt += 1
            batch_text = build_contextual_batch_text(texts, current_target_indices)

            # Smart Model Selection: Use the 75% discounted 'deepseek-v4-pro' until May 31, 2026.
            import datetime
            current_date = datetime.datetime.now(datetime.timezone.utc)
            discount_end_date = datetime.datetime(2026, 5, 31, 15, 59, tzinfo=datetime.timezone.utc)
            
            selected_model = 'deepseek-v4-flash'
            if current_date < discount_end_date:
                selected_model = 'deepseek-v4-pro'
                processor.logger.info(f"🏷️ Using discounted '{selected_model}' model for deep reasoning (valid until May 31).")
            
            try:
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=[
                        {'role': 'system', 'content': processor.get_translation_prompt(target_lang)},
                        {'role': 'user', 'content': batch_text},
                    ],
                    temperature=processor.temperature,
                    max_tokens=4000,
                )

                output = response.choices[0].message.content.strip()
                trans_list = processor._parse_translated_batch_output(
                    output,
                    len(current_target_indices),
                    threshold=0.0,
                )

                if not trans_list:
                    delay = min(20 + attempt * 5, 120)
                    processor.logger.warning(
                        f'⚠️ Batch {i + 1} partial attempt returned empty. Retrying in {delay}s... (Attempt {attempt}/{max_retries})'
                    )
                    time.sleep(delay)
                    if attempt >= max_retries:
                        last_error_msg = f'incomplete response after {max_retries} attempts'
                        break
                    continue

                successful_indices = []
                for rel_idx, trans in enumerate(trans_list):
                    abs_idx = current_target_indices[rel_idx]
                    if trans is None or not str(trans).strip():
                        continue

                    raw_t = str(trans)
                    if target_lang == 'fa':
                        if not any('\u0600' <= c <= '\u06FF' for c in raw_t):
                            continue
                        val = processor.fix_persian_text(processor.strip_english_echo(raw_t))
                    else:
                        val = raw_t

                    final_result[abs_idx] = val
                    successful_indices.append(abs_idx)

                missing_indices = [idx for idx in current_target_indices if idx not in successful_indices]

                if successful_indices:
                    pbar.update(len(successful_indices))

                if successful_indices and output_srt and original_entries:
                    try:
                        write_partial_translation_srt(
                            output_srt=output_srt,
                            original_entries=original_entries,
                            final_result=final_result,
                        )
                    except Exception:
                        pass

                if not missing_indices:
                    success_batch = True
                    time.sleep(1)
                    break

                current_target_indices = missing_indices
                delay = min(20 + attempt * 5, 120)
                processor.logger.warning(
                    f'⚠️ Batch {i + 1} partially incomplete ({len(missing_indices)} lines missing). Retrying missing lines in {delay}s... (Attempt {attempt}/{max_retries})'
                )
                time.sleep(delay)

            except Exception as e:
                error_msg = f'{type(e).__name__}: {str(e)}'
                last_error_msg = error_msg
                if '401' in error_msg or 'Invalid API Key' in error_msg:
                    raise
                if attempt >= max_retries:
                    break
                wait_time = min(60, (2 ** (attempt % 6)) * 5)
                processor.logger.warning(f'Batch {i+1} attempt {attempt}/{max_retries} failed: {error_msg}')
                time.sleep(wait_time)

        if not success_batch:
            gemini_ok = False
            if has_gemini and processor.google_api_key:
                processor.logger.warning(
                    f'⚠️ DeepSeek batch {i+1} failed ({last_error_msg}). Switching to Gemini for this batch...'
                )
                try:
                    from google import genai as _genai

                    gclient = _genai.Client(api_key=processor.google_api_key)
                    models = processor._get_available_gemini_models(gclient)
                    prompt = f"{processor.get_translation_prompt(target_lang)}\n\nLines to translate:\n{batch_text}"
                    for model in models[:3]:
                        try:
                            resp = gclient.models.generate_content(model=model, contents=prompt)
                            tlist = processor._parse_translated_batch_output(resp.text.strip(), len(batch))
                            if None in tlist:
                                tlist = [tlist[j] if tlist[j] is not None else batch[j] for j in range(len(tlist))]
                            if target_lang == 'fa':
                                tlist = [
                                    processor.fix_persian_text(processor.strip_english_echo(t))
                                    if t and has_target_language_chars(t, target_lang)
                                    else batch[j]
                                    for j, t in enumerate(tlist)
                                ]
                            if len(tlist) >= len(batch):
                                for rel_idx, trans in enumerate(tlist[: len(batch)]):
                                    final_result[batch_indices[rel_idx]] = trans
                                if output_srt and original_entries:
                                    try:
                                        write_partial_translation_srt(
                                            output_srt=output_srt,
                                            original_entries=original_entries,
                                            final_result=final_result,
                                        )
                                    except Exception:
                                        pass
                                pbar.update(len(batch))
                                gemini_ok = True
                                processor.logger.info(f'✅ Gemini saved batch {i+1} via {model}')
                                break
                        except Exception as ge:
                            processor.logger.debug(f'Gemini model {model} failed: {ge}')
                except Exception as ge:
                    processor.logger.warning(f'Gemini fallback init failed: {ge}')

            if not gemini_ok:
                processor.logger.error(f'❌ TERMINATING: Batch {i+1} failed on both DeepSeek and Gemini.')
                pbar.close()
                raise RuntimeError(f'Translation halted: batch {i+1} failed — DeepSeek: {last_error_msg}')

    pbar.close()
    return final_result
