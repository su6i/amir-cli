#!/usr/bin/env python3
"""
Easy wrapper for smart_crop.py with better argument handling
"""
import sys
import os

def show_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🔍 Smart Document Scanner - Easy Mode              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  USAGE:                                                      ║
║  ────────────────────────────────────────────────────────   ║
║  python scan.py <input_image> [options]                      ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  OPTIONS:                                                    ║
║  ────────────────────────────────────────────────────────   ║
║  --output=DIR or FILE    Output location (default: ./scans/) ║
║  --smart                 Force smart OCR naming              ║
║  --scan                  Enhanced scan quality               ║
║  --margin=N              White margin in pixels (default:20) ║
║  --preview               Show detection preview only         ║
║  --help                  Show this help                      ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  EXAMPLES:                                                   ║
║  ────────────────────────────────────────────────────────   ║
║  # Basic scan (smart naming to ./scans/)                     ║
║  python scan.py id_card.png                                  ║
║  → scans/LASTNAME_FIRSTNAME_ID.png                           ║
║                                                              ║
║  # Specific output directory                                 ║
║  python scan.py passport.jpg --output=documents/             ║
║  → documents/LASTNAME_FIRSTNAME_ID.png                       ║
║                                                              ║
║  # Exact filename (no smart naming)                          ║
║  python scan.py card.png --output=my_card.png                ║
║  → my_card.png                                               ║
║                                                              ║
║  # Force smart naming even with filename                     ║
║  python scan.py card.png --output=ignored.png --smart        ║
║  → LASTNAME_FIRSTNAME_ID.png                                 ║
║                                                              ║
║  # High quality scan mode                                    ║
║  python scan.py doc.png --scan --margin=30                   ║
║  → scans/LASTNAME_ID.png (enhanced)                          ║
║                                                              ║
║  # Preview detection only (no crop)                          ║
║  python scan.py test.png --preview                           ║
║  → scans/test_preview.png                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

def main():
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        show_help()
        sys.exit(0)
    
    input_file = sys.argv[1]
    
    # Parse options
    output = "./scans/"
    mode = "crop"
    margin = 20
    
    for arg in sys.argv[2:]:
        if arg.startswith('--output='):
            output = arg.split('=', 1)[1]
        elif arg == '--smart':
            mode = "smart"
        elif arg == '--scan':
            mode = "scan"
        elif arg == '--preview':
            mode = "preview"
        elif arg.startswith('--margin='):
            margin = int(arg.split('=', 1)[1])
        elif arg.startswith('--'):
            print(f"⚠️  Unknown option: {arg}")
            print("Run with --help for usage")
            sys.exit(1)
    
    # Create output directory if needed
    if output.endswith('/') and not os.path.exists(output):
        os.makedirs(output, exist_ok=True)
        print(f"📁 Created output directory: {output}")
    
    # Find the actual smart_crop script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    smart_crop = os.path.join(script_dir, "smart_crop_v4_FINAL.py")
    
    if not os.path.exists(smart_crop):
        # Try alternative names
        for name in ["smart_crop_fixed.py", "smart_crop.py"]:
            alt = os.path.join(script_dir, name)
            if os.path.exists(alt):
                smart_crop = alt
                break
    
    if not os.path.exists(smart_crop):
        print("❌ Error: Cannot find smart_crop script!")
        print(f"   Looked in: {script_dir}")
        sys.exit(1)
    
    # Build command
    import subprocess
    cmd = ["python3", smart_crop, input_file, output, str(margin), mode, "9"]
    
    print(f"🚀 Running: {' '.join(cmd)}")
    print("")
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()