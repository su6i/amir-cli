# subtitle/cli.py
# Command Line Interface for Subtitle Engine

import argparse
import os
import sys
from .processor import SubtitleProcessor, LANGUAGE_CONFIG

def main():
    parser = argparse.ArgumentParser(description="Multi-language video subtitle generator")
    parser.add_argument("video", help="Video file path")
    parser.add_argument("-s", "--source", default="en", help="Source language")
    parser.add_argument("-t", "--target", nargs='+', default=['fa'], help="Target language(s)")
    parser.add_argument("-r", "--render", action="store_true", help="Render video")
    
    parser.add_argument("-f", "--force", action="store_true", help="Force re-transcription")
    parser.add_argument("-c", "--correct", action="store_true", help="Correct transcription with AI")
    parser.add_argument("-l", "--limit", type=float, help="Limit transcription duration (seconds)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video):
        print(f"Error: {args.video} not found")
        sys.exit(1)
        
    processor = SubtitleProcessor()
    processor.run_workflow(
        args.video, 
        args.source, 
        args.target, 
        render=args.render, 
        force=args.force,
        correct=args.correct,
        limit=args.limit
    )

if __name__ == "__main__":
    main()
