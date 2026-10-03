"""Bounded stdlib TOML preservation and semantic round-trip proofs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
import tomllib
import unittest

from lunitora_machine import structural_toml as subject


class StructuralTomlTests(unittest.TestCase):
    def entry(self, command="C:/Host Project/tools/lunitora_mcp/.venv/Scripts/python.exe"):
        return {"command": command, "args": ["-B", "-m", "core.godot_server"],
                "cwd": "C:/Host Project/tools/lunitora_mcp", "startup_timeout_sec": 15,
                "tool_timeout_sec": 10, "enabled_tools": ["godot_ping"]}

    def add(self, text, name="lunitora_godot", entry=None):
        document = subject.parse(text)
        document.setdefault("mcp_servers", {})[name] = deepcopy(entry or self.entry())
        return subject.dumps(document)

    def test_fresh_document_round_trips_exact_transport_contract(self):
        document = subject.document()
        document["mcp_servers"] = subject.table()
        document["mcp_servers"]["lunitora_godot"] = subject.item(self.entry())
        output = subject.dumps(document)
        self.assertEqual(tomllib.loads(output), document)
        self.assertEqual(subject.dumps(subject.parse(output)), output)

    def test_append_preserves_original_bytes_comments_and_user_policy(self):
        source = "# operator choice\nmodel = 'custom'\napproval_policy='on-request' # retained\n[mcp_servers.custom]\ncommand='custom command'\nenabled_tools=['read']\n[mcp_servers.custom.tools.read]\napproval_mode='prompt'\n"
        output = self.add(source)
        self.assertTrue(output.startswith(source))
        self.assertEqual(tomllib.loads(output)["mcp_servers"]["custom"],
                         tomllib.loads(source)["mcp_servers"]["custom"])

    def test_noop_preserves_all_formatting_and_comment_bytes(self):
        for source in ("", "# no newline", "a=1 # comment\r\n", "[quoted.'table']\n value = '''literal'''\n"):
            with self.subTest(source=source):
                self.assertEqual(subject.dumps(subject.parse(source)), source)

    def test_owned_repair_preserves_unrelated_table_prefix_and_suffix(self):
        initial = self.add("# before\nmodel='custom'\n")
        suffix = "[mcp_servers.custom]\ncommand='custom command' # untouched\n"
        document = subject.parse(initial + suffix)
        document["mcp_servers"]["lunitora_godot"]["command"] = "C:/New Project/python.exe"
        output = subject.dumps(document)
        self.assertTrue(output.startswith("# before\nmodel='custom'\n"))
        self.assertTrue(output.endswith(suffix))
        self.assertEqual(tomllib.loads(output), document)

    def test_multiline_strings_and_arrays_cannot_fake_owned_table_headers(self):
        for literal in ('"""', "'''"):
            source = "# prefix\ntext=" + literal + "\n[mcp_servers.lunitora_godot]\ncommand='not a table'\n" + literal + "\narray=[\n '[mcp_servers.lunitora_godot]',\n '# deceptive header',\n]\n"
            output = self.add(source)
            self.assertTrue(output.startswith(source))
            self.assertEqual(tomllib.loads(output)["text"], tomllib.loads(source)["text"])

    def test_owned_nested_tables_normalize_without_changing_policy(self):
        source = self.add("") + "[mcp_servers.lunitora_godot.tools.godot_ping]\napproval_mode='prompt'\n[mcp_servers.other]\ncommand='unchanged'\n"
        document = subject.parse(source)
        document["mcp_servers"]["lunitora_godot"]["cwd"] = "C:/Moved Project"
        output = subject.dumps(document)
        self.assertEqual(tomllib.loads(output), document)
        self.assertIn("[mcp_servers.other]\ncommand='unchanged'\n", output)

    def test_quoted_table_components_are_structurally_recognized(self):
        source = self.add("").replace("[mcp_servers.lunitora_godot]", "['mcp_servers'.\"lunitora_godot\"]")
        document = subject.parse(source)
        document["mcp_servers"]["lunitora_godot"]["cwd"] = "C:/Moved Project"
        self.assertEqual(tomllib.loads(subject.dumps(document)), document)

    def test_inline_parent_table_cannot_be_unsafely_extended(self):
        source = "mcp_servers = {custom = {command = 'unchanged'}}\n"
        with self.assertRaisesRegex(ValueError, "preserved"):
            self.add(source)

    def test_owned_dotted_or_inline_layout_repair_fails_closed(self):
        for source in ("mcp_servers.lunitora_godot.command = 'old'\n",
                       "mcp_servers = {lunitora_godot = {command = 'old'}}\n"):
            document = subject.parse(source)
            document["mcp_servers"]["lunitora_godot"]["command"] = "new"
            with self.assertRaisesRegex(ValueError, "preserved"):
                subject.dumps(document)

    def test_unrelated_semantic_changes_and_entry_deletions_are_rejected(self):
        for operation in (lambda document: document.update(model="changed"),
                          lambda document: document["mcp_servers"].update(custom={"command": "new"}),
                          lambda document: document["mcp_servers"].pop("lunitora_godot")):
            document = subject.parse(self.add("model='original'\n"))
            operation(document)
            with self.assertRaisesRegex(ValueError, "preserved"):
                subject.dumps(document)

    def test_crlf_registration_is_preserved_for_new_entry(self):
        source = "model='custom'\r\n# unchanged\r\n"
        output = self.add(source)
        self.assertTrue(output.startswith(source))
        self.assertNotIn("\n", output.replace("\r\n", ""))

    def test_registration_paths_and_quoted_policy_keys_round_trip(self):
        entry = self.entry("C:\\Users\\A 'quoted' name\\path with spaces\\python.exe")
        entry["env"] = {"UNRELATED_CHOICE": "line one\nline two\t\\quoted\""}
        entry["tools"] = {"read.with.dots": {"approval_mode": "prompt"}}
        output = self.add("", entry=entry)
        self.assertEqual(tomllib.loads(output)["mcp_servers"]["lunitora_godot"], entry)

    def test_unrelated_dates_arrays_of_tables_and_nan_are_preserved(self):
        source = "created=2026-10-02\noptional=nan\n[[operator_choices]]\nname='first'\n[[operator_choices]]\nname='second'\n"
        output = self.add(source)
        self.assertTrue(output.startswith(source))
        actual = tomllib.loads(output)
        self.assertTrue(math.isnan(actual["optional"]))
        self.assertEqual([choice["name"] for choice in actual["operator_choices"]], ["first", "second"])

    def test_owned_supported_scalar_types_are_round_trip_safe(self):
        entry = self.entry()
        entry["enabled"] = False
        entry["tool_timeout_sec"] = 10.125
        entry["custom_date"] = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(tomllib.loads(self.add("", entry=entry))["mcp_servers"]["lunitora_godot"], entry)

    def test_unsupported_values_fail_without_displaying_contents(self):
        document = subject.document()
        document["mcp_servers"] = {"lunitora_godot": {"command": object()}}
        with self.assertRaisesRegex(ValueError, "preserved"):
            subject.dumps(document)


if __name__ == "__main__":
    unittest.main()
