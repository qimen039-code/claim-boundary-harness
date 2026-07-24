from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any


@dataclass(frozen=True)
class PythonInlineWriteSink:
    sink_kind: str
    literal_target: str | None
    literal_payload: str | bytes | None

    @property
    def target_is_resolved(self) -> bool:
        return self.literal_target is not None

    @property
    def payload_is_literal(self) -> bool:
        return self.literal_payload is not None


@dataclass(frozen=True)
class PythonInlineWriteAnalysis:
    recognized_inline: bool
    parse_status: str
    sinks: tuple[PythonInlineWriteSink, ...] = ()
    static_write_only: bool = False

    @property
    def write_intent(self) -> bool:
        return bool(self.sinks)

    @property
    def exact_targets(self) -> tuple[str, ...]:
        if not self.sinks or any(not sink.target_is_resolved for sink in self.sinks):
            return ()
        return tuple(
            dict.fromkeys(
                str(sink.literal_target)
                for sink in self.sinks
                if sink.literal_target is not None
            )
        )

    @property
    def unresolved_target(self) -> bool:
        return bool(self.sinks) and any(
            not sink.target_is_resolved for sink in self.sinks
        )

    @property
    def literal_text_payloads(self) -> tuple[str, ...]:
        return tuple(
            sink.literal_payload
            for sink in self.sinks
            if isinstance(sink.literal_payload, str)
        )

    @property
    def contains_unicode_replacement_character(self) -> bool:
        return any(
            "\ufffd" in payload for payload in self.literal_text_payloads
        )


_PYTHON_EXECUTABLE = re.compile(
    r"(?i)^(?:python(?:\d+(?:\.\d+)*)?|py)(?:\.exe)?$"
)


def _powershell_segments(command: str) -> list[list[str]]:
    segments: list[list[str]] = []
    tokens: list[str] = []
    token: list[str] = []
    quote: str | None = None
    index = 0

    def finish_token() -> None:
        if token:
            tokens.append("".join(token))
            token.clear()

    def finish_segment() -> None:
        finish_token()
        if tokens:
            segments.append(list(tokens))
            tokens.clear()

    while index < len(command):
        char = command[index]
        if quote == "'":
            if char == "'" and index + 1 < len(command) and command[index + 1] == "'":
                token.append("'")
                index += 2
                continue
            if char == "'":
                quote = None
            else:
                token.append(char)
            index += 1
            continue
        if quote == '"':
            if char == "`" and index + 1 < len(command):
                token.append(command[index + 1])
                index += 2
                continue
            if char == '"':
                quote = None
            else:
                token.append(char)
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char == "`" and index + 1 < len(command):
            token.append(command[index + 1])
            index += 2
            continue
        if char.isspace():
            finish_token()
            if char in {"\r", "\n"}:
                finish_segment()
            index += 1
            continue
        if char in {";", "|"}:
            finish_segment()
            index += 1
            continue
        if char == "&":
            finish_token()
            if not tokens:
                tokens.append("&")
            else:
                finish_segment()
            index += 1
            continue
        token.append(char)
        index += 1

    finish_segment()
    return segments


def _python_inline_source(segment: list[str]) -> str | None:
    invocation = _python_inline_invocation(segment)
    return invocation[2] if invocation is not None else None


def _python_inline_invocation(
    segment: list[str],
) -> tuple[str, tuple[str, ...], str] | None:
    tokens = list(segment)
    if tokens and tokens[0] == "&":
        tokens = tokens[1:]
    if not tokens:
        return None
    executable = PurePath(tokens[0].replace("\\", "/")).name
    if not _PYTHON_EXECUTABLE.fullmatch(executable):
        return None
    try:
        command_index = tokens.index("-c", 1)
    except ValueError:
        return None
    if any(not token.startswith("-") for token in tokens[1:command_index]):
        return None
    if command_index + 1 >= len(tokens):
        return None
    if command_index + 2 != len(tokens):
        return None
    return (
        executable.casefold(),
        tuple(tokens[1:command_index]),
        tokens[command_index + 1],
    )


def _literal_value(node: ast.AST | None) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return node.value
    return None


def _literal_text(node: ast.AST | None) -> str | None:
    value = _literal_value(node)
    return value if isinstance(value, str) else None


def _call_argument(
    call: ast.Call,
    position: int,
    keyword: str,
) -> ast.AST | None:
    if len(call.args) > position:
        return call.args[position]
    for item in call.keywords:
        if item.arg == keyword:
            return item.value
    return None


def _is_open_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"


def _is_path_constructor(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "Path"
    return (
        isinstance(function, ast.Attribute)
        and function.attr == "Path"
        and isinstance(function.value, ast.Name)
        and function.value.id == "pathlib"
    )


def _path_constructor_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    function = node.func
    if isinstance(function, ast.Name) and function.id == "Path":
        return "Path"
    if (
        isinstance(function, ast.Attribute)
        and function.attr == "Path"
        and isinstance(function.value, ast.Name)
        and function.value.id == "pathlib"
    ):
        return "pathlib.Path"
    return None


def _literal_path_target(call: ast.Call) -> str | None:
    if not call.args or call.keywords:
        return None
    segments = [_literal_text(argument) for argument in call.args]
    if any(segment is None for segment in segments):
        return None
    return str(PurePath(*(segment for segment in segments if segment is not None)))


class _WriteSinkVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.sinks: list[PythonInlineWriteSink] = []

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Attribute):
            if function.attr == "write" and _is_open_call(function.value):
                open_call = function.value
                self.sinks.append(
                    PythonInlineWriteSink(
                        sink_kind="open_write",
                        literal_target=_literal_text(
                            _call_argument(open_call, 0, "file")
                        ),
                        literal_payload=_literal_value(
                            _call_argument(node, 0, "data")
                        ),
                    )
                )
            elif function.attr in {"write_text", "write_bytes"} and _is_path_constructor(
                function.value
            ):
                path_call = function.value
                self.sinks.append(
                    PythonInlineWriteSink(
                        sink_kind="path_" + function.attr,
                        literal_target=_literal_path_target(path_call),
                        literal_payload=_literal_value(
                            _call_argument(node, 0, "data")
                        ),
                    )
                )
        self.generic_visit(node)


def _literal_only_call_arguments(call: ast.Call) -> bool:
    if any(_literal_value(argument) is None for argument in call.args):
        return False
    return all(
        item.arg is not None and _literal_value(item.value) is not None
        for item in call.keywords
    )


def _is_static_open_write_statement(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    call = statement.value
    function = call.func
    if (
        not isinstance(function, ast.Attribute)
        or function.attr != "write"
        or not _is_open_call(function.value)
    ):
        return False
    open_call = function.value
    target = _call_argument(open_call, 0, "file")
    payload = _call_argument(call, 0, "data")
    if _literal_text(target) is None or _literal_value(payload) is None:
        return False
    if len(call.args) != 1 or call.keywords:
        return False
    if any(item.arg == "opener" for item in open_call.keywords):
        return False
    return _literal_only_call_arguments(open_call)


def _is_static_path_write_statement(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    call = statement.value
    function = call.func
    if (
        not isinstance(function, ast.Attribute)
        or function.attr not in {"write_text", "write_bytes"}
        or not _is_path_constructor(function.value)
    ):
        return False
    path_call = function.value
    payload = _call_argument(call, 0, "data")
    if _literal_path_target(path_call) is None or _literal_value(payload) is None:
        return False
    if not call.args or len(call.args) > 4:
        return False
    if any(item.arg is None or item.arg == "data" for item in call.keywords):
        return False
    return _literal_only_call_arguments(call)


def _tree_is_static_write_only(tree: ast.Module) -> bool:
    return bool(tree.body) and all(
        _is_static_open_write_statement(statement)
        or _is_static_path_write_statement(statement)
        for statement in tree.body
    )


def _binding_literal(value: str | bytes) -> object:
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return value


def _literal_call_binding(
    call: ast.Call,
    *,
    omit_positions: set[int] | None = None,
    omit_keywords: set[str] | None = None,
) -> dict[str, object] | None:
    omitted_positions = omit_positions or set()
    omitted_keywords = omit_keywords or set()
    positional: list[object] = []
    for index, argument in enumerate(call.args):
        if index in omitted_positions:
            continue
        value = _literal_value(argument)
        if value is None:
            return None
        positional.append(_binding_literal(value))
    keywords: list[dict[str, object]] = []
    for item in call.keywords:
        if item.arg is None or item.arg in omitted_keywords:
            return None
        value = _literal_value(item.value)
        if value is None:
            return None
        keywords.append({"name": item.arg, "value": _binding_literal(value)})
    return {
        "positional": positional,
        "keywords": sorted(keywords, key=lambda item: str(item["name"])),
    }


def _static_write_operation_binding(statement: ast.stmt) -> dict[str, object] | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    call = statement.value
    function = call.func
    if (
        isinstance(function, ast.Attribute)
        and function.attr == "write"
        and _is_open_call(function.value)
        and _is_static_open_write_statement(statement)
    ):
        open_call = function.value
        open_binding = _literal_call_binding(open_call)
        payload = _literal_value(_call_argument(call, 0, "data"))
        if open_binding is None or payload is None:
            return None
        return {
            "sink_kind": "open_write",
            "open_call": open_binding,
            "payload_type": "bytes" if isinstance(payload, bytes) else "str",
        }
    if (
        isinstance(function, ast.Attribute)
        and function.attr in {"write_text", "write_bytes"}
        and _is_path_constructor(function.value)
        and _is_static_path_write_statement(statement)
    ):
        path_call = function.value
        path_constructor = _path_constructor_name(path_call)
        path_binding = _literal_call_binding(path_call)
        method_binding = _literal_call_binding(
            call,
            omit_positions={0},
            omit_keywords={"data"},
        )
        payload = _literal_value(_call_argument(call, 0, "data"))
        if (
            path_constructor is None
            or path_binding is None
            or method_binding is None
            or payload is None
        ):
            return None
        return {
            "sink_kind": "path_" + function.attr,
            "path_constructor": path_constructor,
            "path_call": path_binding,
            "method_options": method_binding,
            "payload_type": "bytes" if isinstance(payload, bytes) else "str",
        }
    return None


def python_inline_write_operation_binding(command: str) -> dict[str, object] | None:
    """Return a payload-independent binding for one fully static inline write."""

    segments = _powershell_segments(command)
    if len(segments) != 1:
        return None
    invocation = _python_inline_invocation(segments[0])
    if invocation is None:
        return None
    executable, interpreter_options, source = invocation
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return None
    if not _tree_is_static_write_only(tree):
        return None
    operations = [
        _static_write_operation_binding(statement) for statement in tree.body
    ]
    if any(operation is None for operation in operations):
        return None
    return {
        "executable": executable,
        "interpreter_options": list(interpreter_options),
        "operations": [operation for operation in operations if operation is not None],
    }


def analyze_python_inline_write_command(
    command: str,
) -> PythonInlineWriteAnalysis:
    segments = _powershell_segments(command)
    sources = [
        source
        for segment in segments
        if (source := _python_inline_source(segment)) is not None
    ]
    if not sources:
        return PythonInlineWriteAnalysis(
            recognized_inline=False,
            parse_status="not_applicable",
        )

    sinks: list[PythonInlineWriteSink] = []
    parsed_count = 0
    syntax_error_count = 0
    static_write_only = len(sources) == len(segments)
    for source in sources:
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError:
            syntax_error_count += 1
            static_write_only = False
            continue
        parsed_count += 1
        visitor = _WriteSinkVisitor()
        visitor.visit(tree)
        sinks.extend(visitor.sinks)
        static_write_only = static_write_only and _tree_is_static_write_only(tree)

    if parsed_count == 0:
        parse_status = "syntax_error"
    elif syntax_error_count:
        parse_status = "partial"
    else:
        parse_status = "parsed"
    return PythonInlineWriteAnalysis(
        recognized_inline=True,
        parse_status=parse_status,
        sinks=tuple(sinks),
        static_write_only=static_write_only,
    )
