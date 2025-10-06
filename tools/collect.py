"""
Thin shim so legacy calls (tools/collect.py) still work.
Delegates to src.collect:main().
"""
import runpy
import sys
if __name__ == "__main__":
    # Executes src/collect.py in __main__ context (so its main() runs)
    sys.argv = ["src/collect.py"]
    runpy.run_path("src/collect.py", run_name="__main__")
# full Python collector from previous message
