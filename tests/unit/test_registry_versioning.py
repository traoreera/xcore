"""Tests for xcore.registry.versioning."""

import pytest
from xcore.registry.versioning import VersionConstraint, satisfies


class TestVersionConstraint:
    def test_parse_full_semver(self):
        v = VersionConstraint.parse("2.3.1")
        assert v.major == 2
        assert v.minor == 3
        assert v.patch == 1

    def test_parse_two_part(self):
        v = VersionConstraint.parse("2.3")
        assert v.major == 2
        assert v.minor == 3
        assert v.patch == 0

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError, match="invalide"):
            VersionConstraint.parse("not_a_version")

    def test_str(self):
        v = VersionConstraint(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_ordering(self):
        v1 = VersionConstraint.parse("1.0.0")
        v2 = VersionConstraint.parse("2.0.0")
        assert v1 < v2
        assert v2 > v1

    def test_equality(self):
        v1 = VersionConstraint.parse("1.0.0")
        v2 = VersionConstraint.parse("1.0.0")
        assert v1 == v2


class TestSatisfies:
    def test_gte_satisfied(self):
        assert satisfies("2.1.0", ">=2.0") is True

    def test_gte_not_satisfied(self):
        assert satisfies("1.9.0", ">=2.0") is False

    def test_lte_satisfied(self):
        assert satisfies("1.9.0", "<=2.0") is True

    def test_lt_not_satisfied(self):
        assert satisfies("3.0.0", "<3.0") is False

    def test_gt_satisfied(self):
        assert satisfies("3.0.0", ">2.9") is True

    def test_eq_satisfied(self):
        assert satisfies("2.0.0", "==2.0") is True

    def test_ne_satisfied(self):
        assert satisfies("1.0.0", "!=2.0") is True

    def test_ne_not_satisfied(self):
        assert satisfies("2.0.0", "!=2.0") is False

    def test_range_satisfied(self):
        assert satisfies("2.1.0", ">=2.0,<3.0") is True

    def test_range_not_satisfied_upper(self):
        assert satisfies("3.0.0", ">=2.0,<3.0") is False

    def test_invalid_constraint_ignored(self):
        assert satisfies("2.0.0", "bad_constraint") is True

    def test_exact_patch_match(self):
        assert satisfies("2.3.4", "==2.3.4") is True
        assert satisfies("2.3.5", "==2.3.4") is False
