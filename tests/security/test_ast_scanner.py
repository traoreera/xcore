import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from xcore.kernel.security.validation import ASTScanner

def test_ast_scanner_vulnerabilities():
    # Create a temporary directory for the plugin
    plugin_dir = Path("temp_test_plugin")
    src_dir = plugin_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    # Plugin source that uses dangerous functions
    src_file = src_dir / "main.py"
    src_file.write_text("""
def evil_eval():
    e = eval
    e("import os; os.system('ls')")

def evil_getattr():
    g = getattr
    # obj = __import__('os') # This was already blocked
    import json
    g(json, 'loads')('{}')

def evil_dunder():
    # Accessing __globals__ to escape sandbox
    f = lambda: None
    print(f.__globals__)
""")

    scanner = ASTScanner()
    result = scanner.scan(plugin_dir)

    print(f"\nScan passed: {result.passed}")
    for error in result.errors:
        print(f"Error: {error}")
    for warning in result.warnings:
        print(f"Warning: {warning}")

    # Clean up
    import shutil
    shutil.rmtree(plugin_dir)

    # After fix, result.passed should be False if dangerous code is present
    if result.passed:
        print("\n[!] VULNERABILITY CONFIRMED: Scanner passed dangerous code.")
        return False
    else:
        print("\n[+] SUCCESS: Scanner blocked dangerous code.")
        # Check if all 3 vulnerabilities were caught
        error_msgs = "\n".join(result.errors)
        if "eval" in error_msgs and "getattr" in error_msgs and "__globals__" in error_msgs:
            print("[+] All vulnerabilities caught!")
            return True
        else:
            print(f"[!] Some vulnerabilities missed: {error_msgs}")
            return False

if __name__ == "__main__":
    success = test_ast_scanner_vulnerabilities()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
