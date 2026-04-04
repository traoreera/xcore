
import pytest
from pathlib import Path
import json
import yaml
from xcore.kernel.security.signature import sign_plugin, verify_plugin, SignatureError

class MockManifest:
    def __init__(self, name, version, plugin_dir, entry_point="src/main.py"):
        self.name = name
        self.version = version
        self.plugin_dir = Path(plugin_dir)
        self.entry_point = entry_point

def test_signature_bypass_outside_src(tmp_path):
    """
    Test that modifying code outside 'src/' can bypass signature verification
    if entry_point points to it, because the current implementation hardcodes 'src/'.
    """
    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()

    # Create an empty src directory to satisfy current implementation
    (plugin_dir / "src").mkdir()
    (plugin_dir / "src" / "dummy.py").write_text("# dummy")

    # Create an app directory with the actual code
    (plugin_dir / "app").mkdir()
    app_main = plugin_dir / "app" / "main.py"
    app_main.write_text("print('Safe code')")

    # Manifest pointing to app/main.py
    manifest_data = {
        "name": "my_plugin",
        "version": "1.0.0",
        "entry_point": "app/main.py"
    }
    (plugin_dir / "plugin.yaml").write_text(yaml.dump(manifest_data))

    manifest = MockManifest("my_plugin", "1.0.0", plugin_dir, entry_point="app/main.py")
    secret_key = b"secret"

    # Sign the plugin
    sign_plugin(manifest, secret_key)

    # Verify it passes initially
    verify_plugin(manifest, secret_key)

    # NOW: Maliciously modify the code in app/main.py
    app_main.write_text("print('Malicious code')")

    # The signature verification SHOULD fail, but currently it will PASS
    # because it only hashes the 'src/' directory.
    # After the fix, verify_plugin must raise SignatureError when app/main.py is modified.
    with pytest.raises(SignatureError):
        verify_plugin(manifest, secret_key)

def test_signature_root_entry_point(tmp_path):
    """
    Test that modifying code at the root can bypass signature verification
    if entry_point points to it.
    """
    plugin_dir = tmp_path / "root_plugin"
    plugin_dir.mkdir()

    # Create an empty src directory
    (plugin_dir / "src").mkdir()
    (plugin_dir / "src" / "dummy.py").write_text("# dummy")

    # Code at root
    root_main = plugin_dir / "main.py"
    root_main.write_text("print('Safe root code')")

    manifest = MockManifest("root_plugin", "1.0.0", plugin_dir, entry_point="main.py")
    secret_key = b"secret"

    # Sign
    sign_plugin(manifest, secret_key)
    verify_plugin(manifest, secret_key)

    # Modify
    root_main.write_text("print('Malicious root code')")

    try:
        verify_plugin(manifest, secret_key)
        pytest.fail("Signature verification should have failed after modifying code at root!")
    except SignatureError:
        pass
