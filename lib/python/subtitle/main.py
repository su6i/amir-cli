# subtitle/__main__.py
import os
import sys

# Ensure the parent directory is in sys.path so the 'subtitle' package can be imported
# This allows running this file directly with 'python __main__.py' while preserving package context
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.insert(0, package_root)

from subtitle.cli import main

if __name__ == "__main__":
    main()
