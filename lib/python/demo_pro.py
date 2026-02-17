import sys
import os
from subtitle.processor import SubtitleProcessor, SubtitleStyle

def main():
    print("🎬 Starting Pro Subtitle Engine Demo 2026...")
    
    # Check if a video file is provided
    if len(sys.argv) < 2:
        print("Usage: python demo_pro.py <video_path>")
        sys.exit(1)
        
    video_path = sys.argv[1]
    
    # Initialize Processor with Vlog Style (Top center)
    print(f"\nPhase 1: Initializing Processor (VLOG Style)...")
    try:
        processor = SubtitleProcessor(style=SubtitleStyle.VLOG, max_lines=2)
        print(f"✅ Initialized: {processor.style_config.name}")
        print(f"✅ Max Lines: {processor.style_config.max_lines}")
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        sys.exit(1)

    # Simulate Workflow (Dry Run or Real if small)
    print(f"\nPhase 2: Verifying Config for {video_path}...")
    
    # Check for B Nazanin Law compliance in code logic (Mock check)
    if processor.style_config.max_chars <= 40:
        print("✅ Max Chars Constraint: OK")
    else:
        print(f"⚠️ Warning: Max Chars is {processor.style_config.max_chars}")
        
    print("\n✅ System Ready for Full Processing!")
    print("To run full process, use CLI command:")
    print(f"python -m subtitle {video_path} --style vlog --max-lines 2 --speaker")

if __name__ == "__main__":
    main()
