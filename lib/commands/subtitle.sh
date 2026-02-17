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

    # Run the package via module execution (python -m subtitle)
    # We add lib/python to PYTHONPATH so 'subtitle' is recognized as a package
    PYTHONPATH="$LIB_DIR/python:$PYTHONPATH" uv run --project "$SUBTITLE_DIR" python -m subtitle "$@"
    EXIT_CODE=$?
    
    return $EXIT_CODE
}
