import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pcb_copilot.app import main

if __name__ == "__main__":
    main()
