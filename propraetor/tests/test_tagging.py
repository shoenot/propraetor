"""
Tests for the tag prefix configuration and tag generation system.

Covers:
- Config loading, caching, and hot-reload
- Prefix resolution hierarchy (department → company → global → fallback)
- Asset tag generation
- Component tag generation
- Context extraction from model instances
- Edge cases (missing config, malformed config, sequence collisions)
"""

import textwrap
import time
from pathlib import Path
from unittest.mock import patch, PropertyMock

from django.conf import settings
from django.test import TestCase, TransactionTestCase, override_settings

from propraetor.models import (
    Asset,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentType,
    Department,
    Employee,
    Location,
)
from propraetor.tagging import (
    clear_config_cache,
    generate_asset_tag,
    generate_asset_tag_for_instance,
    generate_component_tag,
    generate_component_tag_for_instance,
    get_tag_settings,
    load_config,
    resolve_prefix,
    _extract_company_code,
    _extract_department_name,
    _generate_tag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(path: Path, content: str) -> None:
    """Write a TOML config file, stripping leading indentation."""
    path.write_text(textwrap.dedent(content))


class TaggingTestMixin:
    """Shared setUp/tearDown for tagging tests that manipulate the config file."""

    def _config_path(self) -> Path:
        return Path(settings.BASE_DIR) / "tag_prefixes.toml"

    def setUp(self):
        super().setUp()
        clear_config_cache()
        self._original_config = None
        path = self._config_path()
        if path.exists():
            self._original_config = path.read_text()

    def tearDown(self):
        path = self._config_path()
        if self._original_config is not None:
            path.write_text(self._original_config)
        elif path.exists():
            # If there was no original but we created one during the test,
            # leave it alone — it was the project's real file we preserved.
            pass
        clear_config_cache()
        super().tearDown()

    def _write(self, content: str) -> None:
        _write_config(self._config_path(), content)


# ========================================================================
# Config loading
# ========================================================================

class LoadConfigTests(TaggingTestMixin, TestCase):
    """Tests for load_config() — parsing, caching, and hot-reload."""

    def test_loads_valid_toml(self):
        self._write("""\
            [defaults]
            asset = "XX"
            component = "YY"
        """)
        config = load_config(force_reload=True)
        self.assertEqual(config["defaults"]["asset"], "XX")
        self.assertEqual(config["defaults"]["component"], "YY")

    def test_returns_empty_dict_when_file_missing(self):
        path = self._config_path()
        backup = path.read_text() if path.exists() else None
        try:
            if path.exists():
                path.unlink()
            config = load_config(force_reload=True)
            self.assertEqual(config, {})
        finally:
            if backup is not None:
                path.write_text(backup)

    def test_returns_empty_dict_on_malformed_toml(self):
        self._write("this is [[[not valid toml")
        config = load_config(force_reload=True)
        self.assertEqual(config, {})

    def test_caching_returns_same_object(self):
        self._write("""\
            [defaults]
            asset = "A1"
            component = "C1"
        """)
        first = load_config(force_reload=True)
        second = load_config()
        self.assertIs(first, second)

    def test_force_reload_rereads_file(self):
        self._write("""\
            [defaults]
            asset = "V1"
            component = "V1"
        """)
        load_config(force_reload=True)

        self._write("""\
            [defaults]
            asset = "V2"
            component = "V2"
        """)
        config = load_config(force_reload=True)
        self.assertEqual(config["defaults"]["asset"], "V2")

    def test_hot_reload_on_mtime_change(self):
        """Config should be re-read when the file's mtime changes."""
        self._write("""\
            [defaults]
            asset = "OLD"
            component = "OLD"
        """)
        load_config(force_reload=True)

        # Ensure mtime actually differs (some filesystems have 1s granularity)
        time.sleep(0.05)
        self._write("""\
            [defaults]
            asset = "NEW"
            component = "NEW"
        """)
        # Deliberately NOT passing force_reload — mtime-based detection
        config = load_config()
        self.assertEqual(config["defaults"]["asset"], "NEW")

    def test_clear_config_cache(self):
        self._write("""\
            [defaults]
            asset = "CC"
            component = "CC"
        """)
        load_config(force_reload=True)
        clear_config_cache()

        # After clearing, load_config must re-read
        self._write("""\
            [defaults]
            asset = "DD"
            component = "DD"
        """)
        config = load_config()
        self.assertEqual(config["defaults"]["asset"], "DD")


# ========================================================================
# Tag settings
# ========================================================================

class TagSettingsTests(TaggingTestMixin, TestCase):

    def test_default_tag_settings_from_config(self):
        self._write("""\
            [tag_settings]
            sequence_digits = 6
            separator = "-"
        """)
        ts = get_tag_settings()
        self.assertEqual(ts["sequence_digits"], 6)
        self.assertEqual(ts["separator"], "-")

    def test_fallback_tag_settings_when_missing(self):
        self._write("""\
            [defaults]
            asset = "X"
            component = "Y"
        """)
        ts = get_tag_settings()
        self.assertEqual(ts["sequence_digits"], 5)
        self.assertEqual(ts["separator"], "")

    def test_partial_tag_settings_uses_fallbacks(self):
        self._write("""\
            [tag_settings]
            separator = "."
        """)
        ts = get_tag_settings()
        self.assertEqual(ts["separator"], ".")
        self.assertEqual(ts["sequence_digits"], 5)  # fallback


# ========================================================================
# Prefix resolution
# ========================================================================

class ResolvePrefixTests(TaggingTestMixin, TestCase):

    def _setup_full_config(self):
        self._write("""\
            [defaults]
            asset = "GW"
            component = "CM"

            [companies.ACME]
            asset = "AC"
            component = "AX"

            [companies.ACME.departments.Engineering]
            asset = "AE"
            component = "AEC"

            [companies.GLOBEX]
            asset = "GX"
        """)
        load_config(force_reload=True)

    # -- Global defaults ---------------------------------------------------

    def test_global_default_asset(self):
        self._setup_full_config()
        self.assertEqual(resolve_prefix("asset"), "GW")

    def test_global_default_component(self):
        self._setup_full_config()
        self.assertEqual(resolve_prefix("component"), "CM")

    # -- Company-level overrides ------------------------------------------

    def test_company_override_asset(self):
        self._setup_full_config()
        self.assertEqual(resolve_prefix("asset", company_code="ACME"), "AC")

    def test_company_override_component(self):
        self._setup_full_config()
        self.assertEqual(resolve_prefix("component", company_code="ACME"), "AX")

    def test_company_partial_override_falls_back_for_missing_type(self):
        """GLOBEX only defines asset — component should fall back to global."""
        self._setup_full_config()
        self.assertEqual(resolve_prefix("asset", company_code="GLOBEX"), "GX")
        self.assertEqual(resolve_prefix("component", company_code="GLOBEX"), "CM")

    def test_unknown_company_falls_back_to_global(self):
        self._setup_full_config()
        self.assertEqual(resolve_prefix("asset", company_code="NOPE"), "GW")
        self.assertEqual(resolve_prefix("component", company_code="NOPE"), "CM")

    # -- Department-level overrides ----------------------------------------

    def test_department_override_asset(self):
        self._setup_full_config()
        self.assertEqual(
            resolve_prefix("asset", company_code="ACME", department_name="Engineering"),
            "AE",
        )

    def test_department_override_component(self):
        self._setup_full_config()
        self.assertEqual(
            resolve_prefix("component", company_code="ACME", department_name="Engineering"),
            "AEC",
        )

    def test_unknown_department_falls_back_to_company(self):
        self._setup_full_config()
        self.assertEqual(
            resolve_prefix("asset", company_code="ACME", department_name="Sales"),
            "AC",
        )

    def test_department_without_company_is_ignored(self):
        """department_name without company_code should just return global."""
        self._setup_full_config()
        self.assertEqual(
            resolve_prefix("asset", department_name="Engineering"),
            "GW",
        )

    # -- Built-in fallback -------------------------------------------------

    def test_builtin_fallback_when_no_defaults_section(self):
        self._write("""\
            [tag_settings]
            sequence_digits = 4
        """)
        load_config(force_reload=True)
        self.assertEqual(resolve_prefix("asset"), "ASSET")
        self.assertEqual(resolve_prefix("component"), "COMP")

    def test_builtin_fallback_when_config_missing(self):
        path = self._config_path()
        backup = path.read_text() if path.exists() else None
        try:
            if path.exists():
                path.unlink()
            clear_config_cache()
            self.assertEqual(resolve_prefix("asset"), "ASSET")
            self.assertEqual(resolve_prefix("component"), "COMP")
        finally:
            if backup is not None:
                path.write_text(backup)

    def test_unknown_entity_type_returns_tag(self):
        """An entity type with no fallback should return 'TAG'."""
        self._write("""\
            [defaults]
            asset = "GW"
            component = "CM"
        """)
        load_config(force_reload=True)
        self.assertEqual(resolve_prefix("widget"), "TAG")


# ========================================================================
# Context extraction helpers
# ========================================================================

class ExtractHelpersTests(TestCase):

    def test_extract_company_code_from_company(self):
        c = Company(name="Test Corp", code="TC")
        self.assertEqual(_extract_company_code(c), "TC")

    def test_extract_company_code_none(self):
        self.assertIsNone(_extract_company_code(None))

    def test_extract_company_code_blank(self):
        c = Company(name="No Code", code="")
        self.assertIsNone(_extract_company_code(c))

    def test_extract_department_name(self):
        d = Department(name="IT")
        self.assertEqual(_extract_department_name(d), "IT")

    def test_extract_department_name_none(self):
        self.assertIsNone(_extract_department_name(None))


# ========================================================================
# Tag generation (integration with database)
# ========================================================================

class TagGenerationTests(TaggingTestMixin, TransactionTestCase):
    """Integration tests that create real database rows."""

    def setUp(self):
        super().setUp()
        self._write("""\
            [tag_settings]
            sequence_digits = 5
            separator = ""

            [defaults]
            asset = "GW"
            component = "CM"

            [companies.TC]
            asset = "TC"
            component = "TX"

            [companies.TC.departments.Eng]
            asset = "TE"
        """)
        load_config(force_reload=True)

        # Shared fixtures
        self.company = Company.objects.create(name="Test Corp", code="TC")
        self.location = Location.objects.create(name="HQ")
        self.department = Department.objects.create(
            name="Eng", company=self.company,
        )
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category, manufacturer="Lenovo", model_name="T480",
        )
        self.comp_type = ComponentType.objects.create(type_name="RAM")

    # -- Asset tag generation ----------------------------------------------

    def test_generate_asset_tag_global(self):
        tag = generate_asset_tag()
        self.assertTrue(tag.startswith("GW"))
        self.assertEqual(tag, "GW00001")

    def test_generate_asset_tag_sequential(self):
        Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        tag = generate_asset_tag()
        self.assertEqual(tag, "GW00002")

    def test_generate_asset_tag_company_override(self):
        tag = generate_asset_tag(company=self.company)
        self.assertEqual(tag, "TC00001")

    def test_generate_asset_tag_department_override(self):
        tag = generate_asset_tag(company=self.company, department=self.department)
        self.assertEqual(tag, "TE00001")

    def test_generate_asset_tag_skips_existing(self):
        """If a tag already exists, the generator should skip to the next."""
        Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        Asset.objects.create(
            asset_tag="GW00002", asset_model=self.asset_model, company=self.company,
        )
        tag = generate_asset_tag()
        self.assertEqual(tag, "GW00003")

    def test_generate_asset_tag_handles_gaps(self):
        """Tags with gaps should still use max+1."""
        Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        Asset.objects.create(
            asset_tag="GW00005", asset_model=self.asset_model, company=self.company,
        )
        tag = generate_asset_tag()
        self.assertEqual(tag, "GW00006")

    # -- Component tag generation ------------------------------------------

    def test_generate_component_tag_global(self):
        tag = generate_component_tag()
        self.assertEqual(tag, "CM00001")

    def test_generate_component_tag_company_override(self):
        tag = generate_component_tag(company=self.company)
        self.assertEqual(tag, "TX00001")

    def test_generate_component_tag_sequential(self):
        parent = Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        Component.objects.create(
            component_tag="CM00001", component_type=self.comp_type,
            parent_asset=parent, status="installed",
        )
        tag = generate_component_tag()
        self.assertEqual(tag, "CM00002")

    # -- Tag is NOT based on type or model ---------------------------------

    def test_component_tag_independent_of_type(self):
        """Different component types should share the same prefix sequence."""
        ssd_type = ComponentType.objects.create(type_name="SSD")
        parent = Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        Component.objects.create(
            component_tag="CM00001", component_type=self.comp_type,
            parent_asset=parent, status="installed",
        )
        # Next tag should be CM00002 regardless of type being SSD vs RAM
        tag = generate_component_tag()
        self.assertEqual(tag, "CM00002")
        self.assertFalse(tag.startswith("SSD"))
        self.assertFalse(tag.startswith("RAM"))

    def test_asset_tag_independent_of_model(self):
        """Different asset models should share the same prefix sequence."""
        other_model = AssetModel.objects.create(
            category=self.category, manufacturer="Dell", model_name="XPS 15",
        )
        Asset.objects.create(
            asset_tag="GW00001", asset_model=self.asset_model, company=self.company,
        )
        Asset.objects.create(
            asset_tag="GW00002", asset_model=other_model, company=self.company,
        )
        tag = generate_asset_tag()
        self.assertEqual(tag, "GW00003")


# ========================================================================
# Instance-based generation (auto-tag on save)
# ========================================================================

class InstanceTagGenerationTests(TaggingTestMixin, TransactionTestCase):
    """Tests for generate_*_tag_for_instance and model.save() auto-tagging."""

    def setUp(self):
        super().setUp()
        self._write("""\
            [tag_settings]
            sequence_digits = 5
            separator = ""

            [defaults]
            asset = "GW"
            component = "CM"

            [companies.TC]
            asset = "TC"
            component = "TX"

            [companies.TC.departments.Eng]
            asset = "TE"
            component = "TEC"
        """)
        load_config(force_reload=True)

        self.company = Company.objects.create(name="Test Corp", code="TC")
        self.location = Location.objects.create(name="HQ")
        self.department = Department.objects.create(
            name="Eng", company=self.company,
        )
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category, manufacturer="Lenovo", model_name="T480",
        )
        self.comp_type = ComponentType.objects.create(type_name="RAM")
        self.employee = Employee.objects.create(
            name="Alice",
            department=self.department,
            status="active",
        )

    # -- Asset save() auto-generation --------------------------------------

    def test_asset_auto_generates_tag_on_save(self):
        asset = Asset(asset_model=self.asset_model, company=self.company)
        asset.save()
        self.assertTrue(asset.asset_tag.startswith("TC"))
        self.assertEqual(asset.asset_tag, "TC00001")

    def test_asset_preserves_manually_set_tag(self):
        asset = Asset(
            asset_tag="CUSTOM-999",
            asset_model=self.asset_model,
            company=self.company,
        )
        asset.save()
        self.assertEqual(asset.asset_tag, "CUSTOM-999")

    def test_asset_auto_tag_uses_department_from_assignee(self):
        asset = Asset(
            asset_model=self.asset_model,
            company=self.company,
            assigned_to=self.employee,
        )
        asset.save()
        self.assertTrue(asset.asset_tag.startswith("TE"))

    def test_asset_auto_tag_global_when_no_company(self):
        asset = Asset(asset_model=self.asset_model)
        asset.save()
        self.assertTrue(asset.asset_tag.startswith("GW"))

    # -- Component save() auto-generation ----------------------------------

    def test_component_auto_generates_tag_on_save(self):
        parent = Asset.objects.create(
            asset_tag="TC00001", asset_model=self.asset_model, company=self.company,
        )
        comp = Component(
            component_type=self.comp_type,
            parent_asset=parent,
            status="installed",
        )
        comp.save()
        self.assertTrue(comp.component_tag.startswith("TX"))
        self.assertEqual(comp.component_tag, "TX00001")

    def test_component_preserves_manually_set_tag(self):
        parent = Asset.objects.create(
            asset_tag="TC00001", asset_model=self.asset_model, company=self.company,
        )
        comp = Component(
            component_tag="MANUAL-001",
            component_type=self.comp_type,
            parent_asset=parent,
            status="installed",
        )
        comp.save()
        self.assertEqual(comp.component_tag, "MANUAL-001")

    def test_component_auto_tag_global_when_no_parent(self):
        comp = Component(component_type=self.comp_type, status="spare")
        comp.save()
        self.assertTrue(comp.component_tag.startswith("CM"))

    def test_component_auto_tag_uses_parent_department(self):
        parent = Asset.objects.create(
            asset_model=self.asset_model,
            company=self.company,
            assigned_to=self.employee,
            asset_tag="TE00001",
        )
        comp = Component(
            component_type=self.comp_type,
            parent_asset=parent,
            status="installed",
        )
        comp.save()
        self.assertTrue(comp.component_tag.startswith("TEC"))

    # -- generate_*_for_instance directly ----------------------------------

    def test_generate_asset_tag_for_instance_no_company(self):
        asset = Asset(asset_model=self.asset_model)
        tag = generate_asset_tag_for_instance(asset)
        self.assertTrue(tag.startswith("GW"))

    def test_generate_component_tag_for_instance_no_parent(self):
        comp = Component(component_type=self.comp_type, status="spare")
        tag = generate_component_tag_for_instance(comp)
        self.assertTrue(tag.startswith("CM"))


# ========================================================================
# Separator and digits variations
# ========================================================================

class FormattingTests(TaggingTestMixin, TransactionTestCase):

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Desktop")
        self.asset_model = AssetModel.objects.create(
            category=self.category, manufacturer="HP", model_name="ProDesk",
        )
        self.comp_type = ComponentType.objects.create(type_name="CPU")

    def test_separator_dash(self):
        self._write("""\
            [tag_settings]
            sequence_digits = 4
            separator = "-"

            [defaults]
            asset = "HQ"
            component = "CP"
        """)
        load_config(force_reload=True)
        tag = generate_asset_tag()
        self.assertEqual(tag, "HQ-0001")

    def test_six_digit_sequence(self):
        self._write("""\
            [tag_settings]
            sequence_digits = 6
            separator = ""

            [defaults]
            asset = "AA"
            component = "BB"
        """)
        load_config(force_reload=True)
        tag = generate_asset_tag()
        self.assertEqual(tag, "AA000001")

    def test_separator_dot(self):
        self._write("""\
            [tag_settings]
            sequence_digits = 3
            separator = "."

            [defaults]
            asset = "X"
            component = "Y"
        """)
        load_config(force_reload=True)
        tag = generate_component_tag()
        self.assertEqual(tag, "Y.001")


# ========================================================================
# Isolation: different prefixes don't collide
# ========================================================================

class PrefixIsolationTests(TaggingTestMixin, TransactionTestCase):
    """Tags under different prefixes maintain independent sequences."""

    def setUp(self):
        super().setUp()
        self._write("""\
            [tag_settings]
            sequence_digits = 5
            separator = ""

            [defaults]
            asset = "GW"
            component = "CM"

            [companies.AA]
            asset = "AA"

            [companies.BB]
            asset = "BB"
        """)
        load_config(force_reload=True)

        self.company_a = Company.objects.create(name="Company A", code="AA")
        self.company_b = Company.objects.create(name="Company B", code="BB")
        self.category = Category.objects.create(name="Server")
        self.model = AssetModel.objects.create(
            category=self.category, manufacturer="Dell", model_name="R740",
        )

    def test_different_company_prefixes_independent(self):
        Asset.objects.create(
            asset_tag="AA00001", asset_model=self.model, company=self.company_a,
        )
        Asset.objects.create(
            asset_tag="AA00002", asset_model=self.model, company=self.company_a,
        )
        # Company B should start at 1, not 3
        tag_b = generate_asset_tag(company=self.company_b)
        self.assertEqual(tag_b, "BB00001")

        # Company A should continue at 3
        tag_a = generate_asset_tag(company=self.company_a)
        self.assertEqual(tag_a, "AA00003")

    def test_global_and_company_prefixes_independent(self):
        Asset.objects.create(
            asset_tag="GW00001", asset_model=self.model, company=self.company_a,
        )
        tag_co = generate_asset_tag(company=self.company_a)
        self.assertEqual(tag_co, "AA00001")

        tag_gl = generate_asset_tag()
        self.assertEqual(tag_gl, "GW00002")


# ========================================================================
# Edge cases
# ========================================================================

class EdgeCaseTests(TaggingTestMixin, TransactionTestCase):

    def setUp(self):
        super().setUp()
        self._write("""\
            [tag_settings]
            sequence_digits = 5
            separator = ""

            [defaults]
            asset = "GW"
            component = "CM"
        """)
        load_config(force_reload=True)

        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category, manufacturer="Apple", model_name="MacBook Pro",
        )
        self.comp_type = ComponentType.objects.create(type_name="SSD")

    def test_existing_non_numeric_suffixes_are_ignored(self):
        """Tags with non-numeric suffixes shouldn't break sequence detection."""
        Asset.objects.create(
            asset_tag="GW00003", asset_model=self.asset_model,
        )
        Asset.objects.create(
            asset_tag="GWlegacy", asset_model=self.asset_model,
        )
        tag = generate_asset_tag()
        self.assertEqual(tag, "GW00004")

    def test_company_with_no_code_uses_global(self):
        company_no_code = Company.objects.create(name="No Code Inc")
        tag = generate_asset_tag(company=company_no_code)
        self.assertTrue(tag.startswith("GW"))

    def test_multiple_saves_dont_overwrite_tag(self):
        """Saving an existing asset again should NOT regenerate its tag."""
        asset = Asset(asset_model=self.asset_model)
        asset.save()
        original_tag = asset.asset_tag
        asset.notes = "updated"
        asset.save()
        self.assertEqual(asset.asset_tag, original_tag)

    def test_multiple_component_saves_dont_overwrite_tag(self):
        comp = Component(component_type=self.comp_type, status="spare")
        comp.save()
        original_tag = comp.component_tag
        comp.notes = "updated"
        comp.save()
        self.assertEqual(comp.component_tag, original_tag)

    def test_tags_unique_across_rapid_creation(self):
        """Rapidly creating multiple assets should yield unique tags."""
        tags = set()
        for _ in range(20):
            asset = Asset(asset_model=self.asset_model)
            asset.save()
            tags.add(asset.asset_tag)
        self.assertEqual(len(tags), 20)

    def test_component_tags_unique_across_rapid_creation(self):
        tags = set()
        for _ in range(20):
            comp = Component(component_type=self.comp_type, status="spare")
            comp.save()
            tags.add(comp.component_tag)
        self.assertEqual(len(tags), 20)