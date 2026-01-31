#!/bin/bash

run_subtitle() {
    # Define location of the python project
    SUBTITLE_DIR="$LIB_DIR/python/subtitle"
    
    # Check if directory exists
    if [[ ! -d "$SUBTITLE_DIR" ]]; then
        echo "❌ Error: Subtitle module not found at $SUBTITLE_DIR"
        return 1
    fi
    
    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        echo "❌ Error: 'uv' is not installed. Please install it first (curl -LsSf https://astral.sh/uv/install.sh | sh)"
        return 1
    fi

    # Run the script with uv
    # We use --project to specify the environment, but execute main.py directly
    # This keeps the CWD as the user's directory so relative paths work properly
    uv run --project "$SUBTITLE_DIR" python "$SUBTITLE_DIR/main.py" "$@"
    EXIT_CODE=$?
    
    return $EXIT_CODE
}
