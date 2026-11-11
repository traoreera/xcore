"""The kernel reads YAML through the C loader when it is available (issue #305, point 4).

`yaml.safe_load` uses the pure-Python loader even when PyYAML is built against libyaml. The kernel
reads one manifest per plugin at boot, and the sandbox worker re-reads its own at every recycle, so
this is pure startup time: measured 3.5 ms -> 0.37 ms on a real manifest.

What these tests defend:
- `yamlio.safe_load` parses exactly what `yaml.safe_load` parses (same result, same types);
- it is just as SAFE: an arbitrary-object tag is refused, like `SafeLoader` (the whole point of not
  reaching for `yaml.load` with the full loader);
- it works whether or not the C loader is present, so an installation without libyaml is slower and
  nothing more.
"""

import io

import pytest
import yaml

from xcore.kernel import yamlio

DOC = """
name: te
version: 1.0.0
enabled: true
retries: 3
ratio: 1.5
nothing: null
permissions:
  - resource: "db.*"
    actions: [read, write]
tags: {a: 1, b: [2, 3]}
"""


class TestParity:
    def test_it_parses_what_safe_load_parses(self):
        assert yamlio.safe_load(DOC) == yaml.safe_load(DOC)

    def test_types_are_the_same_not_just_the_shape(self):
        parsed = yamlio.safe_load(DOC)
        assert parsed["enabled"] is True
        assert isinstance(parsed["retries"], int) and isinstance(parsed["ratio"], float)
        assert parsed["nothing"] is None
        assert parsed["tags"] == {"a": 1, "b": [2, 3]}

    def test_it_reads_a_stream_as_well_as_a_string(self):
        assert yamlio.safe_load(io.StringIO(DOC)) == yaml.safe_load(DOC)

    @pytest.mark.parametrize("empty", ["", "\n", "---\n"])
    def test_an_empty_document_is_none_as_everywhere(self, empty):
        assert yamlio.safe_load(empty) is None


class TestSafety:
    def test_an_arbitrary_object_tag_is_refused(self):
        """Same safety as SafeLoader: a manifest must never be able to build a Python object."""
        with pytest.raises(yaml.YAMLError):
            yamlio.safe_load("!!python/object/apply:os.system ['echo nope']")

    def test_a_syntax_error_is_a_yaml_error_not_a_crash(self):
        with pytest.raises(yaml.YAMLError):
            yamlio.safe_load("a: [1, 2\nb: 3")


def test_the_fast_flag_says_which_loader_is_in_use():
    """Informational, and it is what a diagnostic reads: it must stay a boolean, never raise."""
    assert isinstance(yamlio.FAST, bool)
    if yaml.__with_libyaml__:  # pragma: no branch - dépend de l'installation
        assert (
            yamlio.FAST
        ), "PyYAML est compilé avec libyaml : le loader C devrait être pris"
