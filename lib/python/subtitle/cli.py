# subtitle/cli.py
# Command Line Interface for Subtitle Engine

import argparse
import os
import sys
from .processor import SubtitleProcessor, SubtitleStyle

def main():
    parser = argparse.ArgumentParser(description="Multi-language video subtitle generator (2026 Pro Edition)")
    parser.add_argument("video", help="Video file path")
    parser.add_argument("-s", "--source", default="en", help="Source language")
    parser.add_argument("-t", "--target", nargs='+', default=['fa'], help="Target language(s)")
    parser.add_argument("-r", "--render", action="store_true", help="Render video")
    
    parser.add_argument("-f", "--force", action="store_true", help="Force re-transcription")
    parser.add_argument("-c", "--correct", action="store_true", help="Correct transcription with AI")
    parser.add_argument("-l", "--limit", type=float, help="Limit transcription duration (seconds)")
    
    # New Pro Arguments
    parser.add_argument("--style", type=str, default="lecture", choices=[e.value for e in SubtitleStyle], help="Subtitle style template")
    parser.add_argument("--max-lines", type=int, default=1, help="Maximum lines per subtitle (1 or 2)")
    parser.add_argument("--speaker", action="store_true", help="Enable Speaker Diarization")

    # BERT options (optional)
    parser.add_argument("--use-bert", action="store_true", help="Enable BERT masked-LM collocation scoring")
    parser.add_argument("--bert-model", type=str, help="BERT model name (e.g., bert-base-uncased)")
    
    # Style Overrides
    parser.add_argument("--alignment", type=int, help="ASS alignment (2=Bottom, 8=Top, 5=Center)")
    parser.add_argument("--font-size", type=int, help="Primary font size (e.g., 25)")
    parser.add_argument("--sec-font-size", type=int, help="Secondary font size (e.g., 18)")
    
    # Visual Overrides (Pro)
    parser.add_argument("--shadow", type=int, help="Shadow depth (default: 0)")
    parser.add_argument("--outline", type=int, help="Outline width (default: 2)")
    parser.add_argument("--back-color", type=str, help="Background color (ASS hex, e.g., &H80000000)")
    parser.add_argument("--primary-color", type=str, help="Primary color (ASS hex, e.g., &H00FFFFFF)")
    
    # AI Tuning (Pro)
    parser.add_argument("--llm", type=str, default="deepseek", choices=["deepseek", "gemini", "litellm"], help="LLM bridge for translation")
    parser.add_argument("--model", type=str, help="Specific model name (required for LiteLLM, e.g., gpt-4o)")
    parser.add_argument("--whisper-model", type=str, default="large-v3", help="Whisper model size (e.g., large-v3, turbo)")
    parser.add_argument("--initial-prompt", type=str, help="Whisper initial prompt (context)")
    parser.add_argument("--temperature", type=float, default=0.0, help="Model temperature (0.0-1.0)")
    parser.add_argument("--openai-fallback", action="store_true", help="Use OpenAI if DeepSeek fails")
    
    # Logic Overrides (Pro)
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum subtitle duration (seconds)")

    args = parser.parse_args()
    
    if not os.path.exists(args.video):
        print(f"Error: {args.video} not found")
        sys.exit(1)
        
    # Convert string style to Enum
    style_enum = SubtitleStyle(args.style)
        
    processor = SubtitleProcessor(
        style=style_enum, 
        model_size=args.whisper_model,
        max_lines=args.max_lines,
        alignment=args.alignment,
        font_size=args.font_size,
        sec_font_size=args.sec_font_size,
        shadow=args.shadow,
        outline=args.outline,
        back_color=args.back_color,
        primary_color=args.primary_color,
        initial_prompt=args.initial_prompt,
        temperature=args.temperature,
        use_openai_fallback=args.openai_fallback,
        min_duration=args.min_duration,
        llm=args.llm,
        custom_model=args.model
        ,use_bert=args.use_bert,
        bert_model=args.bert_model
    )
    processor.run_workflow(
        args.video, 
        args.source, 
        args.target, 
        render=args.render, 
        force=args.force,
        correct=args.correct,
        limit=args.limit,
        detect_speakers=args.speaker
    )

if __name__ == "__main__":
    main()
