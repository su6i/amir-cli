import os
from typing import Any, Dict, List, Optional


def run_finalize_stage(
    processor,
    result: Dict[str, Any],
    original_base: str,
    original_stem: str,
    original_dir: str,
    source_lang: str,
    target_langs: List[str],
    platforms: Optional[List[str]] = None,
    prompt_file: Optional[str] = None,
    post_langs: Optional[List[str]] = None,
    save_formats: Optional[List[str]] = None,
) -> None:
    """Run post generation, document export, and output bundling stages."""
    if platforms:
        try:
            saved_posts = processor.generate_posts(
                original_base,
                source_lang,
                result,
                platforms=platforms,
                prompt_file=prompt_file,
                post_langs=post_langs,
            )
            if saved_posts:
                result["posts"] = saved_posts
        except Exception as pe:
            processor.logger.warning(f"⚠️ Post generation failed (workflow continues): {pe}")

    if save_formats:
        try:
            from subtitle.exporter import export_subtitles

            export_langs = set(target_langs) if target_langs else {source_lang}

            srt_paths = {
                lang: path
                for lang, path in result.items()
                if isinstance(path, str) and path.endswith(".srt") and lang in export_langs
            }

            if srt_paths:
                created = export_subtitles(
                    srt_paths=srt_paths,
                    base_name=original_stem,
                    formats=save_formats,
                    output_dir=original_dir,
                    title=original_stem.replace("_", " ").replace("-", " "),
                    logger=processor.logger,
                )
                if created:
                    result["exported_docs"] = created
            else:
                processor.logger.warning("⚠️ No SRT files available for document export.")
        except Exception as exp_e:
            processor.logger.warning(f"⚠️ Document export failed: {exp_e}")

    output_files = processor._collect_existing_output_files(result)
    bundle_path = processor._bundle_outputs_zip(original_base, output_files)
    if bundle_path and os.path.exists(bundle_path):
        result["bundle_zip"] = bundle_path
        output_files.append(os.path.abspath(bundle_path))

    if output_files:
        processor.logger.info("📦 Output files:")
        for p in output_files:
            processor.logger.info(f"   - {os.path.basename(p)}")