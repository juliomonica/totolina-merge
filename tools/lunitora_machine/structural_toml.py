"""Bounded stdlib TOML writes for already admitted setup-owned MCP entries.

tomllib is authoritative for syntax and values. Source spans are used only to
preserve unrelated bytes; the complete result must parse to the desired values.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time
import json
import math
import re
import tomllib

_OWNED_NAMES = {"lunitora_godot", "lunitora_photoshop"}
_FAILURE = "Codex TOML layout cannot be safely updated; existing configuration was preserved."
_SENTINEL = "__lunitora_header_sentinel__"


class Document(dict):
    def __init__(self, source="", values=None):
        super().__init__(deepcopy(values or {}))
        self.source = source


def parse(source):
    return Document(source, tomllib.loads(source))


def document():
    return Document()


def table():
    return {}


def item(value):
    return deepcopy(value)


def _same(first, second):
    if type(first) is not type(second):
        return False
    if isinstance(first, dict):
        return first.keys() == second.keys() and all(_same(first[key], second[key]) for key in first)
    if isinstance(first, list):
        return len(first) == len(second) and all(_same(a, b) for a, b in zip(first, second))
    if isinstance(first, float) and math.isnan(first):
        return math.isnan(second)
    return first == second


def _key(value):
    if not isinstance(value, str):
        raise ValueError(_FAILURE)
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else json.dumps(value, ensure_ascii=False)


def _value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is float:
        return "nan" if math.isnan(value) else ("inf" if value == math.inf else "-inf" if value == -math.inf else repr(value))
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_value(element) for element in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(_key(key) + " = " + _value(element) for key, element in value.items()) + " }"
    raise ValueError(_FAILURE)


def _render_entry(name, entry, newline):
    if not isinstance(entry, dict):
        raise ValueError(_FAILURE)
    lines = ["[mcp_servers." + _key(name) + "]"]
    lines.extend(_key(key) + " = " + _value(value) for key, value in entry.items())
    return newline.join(lines) + newline


def _header_path(header):
    parsed = tomllib.loads(header + "\n" + _SENTINEL + " = true\n")
    path, value = [], parsed
    while isinstance(value, dict) and _SENTINEL not in value:
        if len(value) != 1:
            raise ValueError(_FAILURE)
        key, value = next(iter(value.items()))
        path.append(key)
        if isinstance(value, list):
            if len(value) != 1:
                raise ValueError(_FAILURE)
            value = value[0]
    if value != {_SENTINEL: True}:
        raise ValueError(_FAILURE)
    return tuple(path)


def _headers(source):
    """Recognize table statements, never brackets inside values or comments."""
    headers = []
    index, line_start, quote, triple, escaped = 0, 0, None, False, False
    square, curly, comment, statement = 0, 0, False, False
    while index < len(source):
        char = source[index]
        if comment:
            if char == "\n":
                comment = False
                line_start = index + 1
                if square == 0 and curly == 0:
                    statement = False
            index += 1
            continue
        if quote is not None:
            if quote == '"' and escaped:
                escaped = False
                index += 1
                continue
            if quote == '"' and char == "\\":
                escaped = True
                index += 1
                continue
            if char == quote:
                if triple and source[index:index + 3] == quote * 3:
                    quote, triple = None, False
                    index += 3
                    continue
                if not triple:
                    quote = None
            index += 1
            continue
        if char in " \t\r":
            index += 1
            continue
        if char == "\n":
            line_start = index + 1
            if square == 0 and curly == 0:
                statement = False
            index += 1
            continue
        if char == "#":
            comment = True
            index += 1
            continue
        if not statement and char == "[" and square == 0 and curly == 0:
            end = source.find("\n", index)
            end = len(source) if end == -1 else end + 1
            header = source[index:end].rstrip("\r\n")
            headers.append((line_start, _header_path(header)))
            index = end
            line_start, statement = end, False
            continue
        statement = True
        if char in "\"'":
            quote = char
            triple = source[index:index + 3] == char * 3
            index += 3 if triple else 1
            continue
        if char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
        index += 1
    return headers


def dumps(value):
    if not isinstance(value, Document):
        raise ValueError(_FAILURE)
    source = value.source
    original = tomllib.loads(source)
    desired = dict(value)
    if _same(original, desired):
        return source
    before = {key: item for key, item in original.items() if key != "mcp_servers"}
    after = {key: item for key, item in desired.items() if key != "mcp_servers"}
    old_servers, new_servers = original.get("mcp_servers", {}), desired.get("mcp_servers", {})
    if not _same(before, after) or not isinstance(old_servers, dict) or not isinstance(new_servers, dict):
        raise ValueError(_FAILURE)
    changed = [name for name in old_servers.keys() | new_servers.keys()
               if name not in old_servers or name not in new_servers or not _same(old_servers[name], new_servers[name])]
    if not set(changed) <= _OWNED_NAMES or any(name not in new_servers for name in changed):
        raise ValueError(_FAILURE)
    newline = "\r\n" if "\r\n" in source else "\n"
    headers = _headers(source)
    replacements, additions = [], []
    for name in sorted(changed):
        entry = _render_entry(name, new_servers[name], newline)
        if name not in old_servers:
            additions.append(entry)
            continue
        spans = [(start, headers[position + 1][0] if position + 1 < len(headers) else len(source))
                 for position, (start, path) in enumerate(headers) if path[:2] == ("mcp_servers", name)]
        exact = [path for _, path in headers if path == ("mcp_servers", name)]
        if len(exact) != 1 or not spans:
            raise ValueError(_FAILURE)
        # Only source spans belonging to this admitted entry can be normalized.
        replacements.extend((start, end, entry if position == 0 else "")
                            for position, (start, end) in enumerate(spans))
    output = source
    for start, end, replacement in sorted(replacements, reverse=True):
        output = output[:start] + replacement + output[end:]
    for entry in additions:
        output += ("" if not output or output.endswith(("\n", "\r")) else newline) + newline + entry
    try:
        actual = tomllib.loads(output)
    except tomllib.TOMLDecodeError:
        raise ValueError(_FAILURE) from None
    if not _same(actual, desired):
        raise ValueError(_FAILURE)
    return output
