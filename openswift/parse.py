"""A small reader for the SwiftUI shapes OpenSwift knows how to draw.

It is not a Swift parser. It walks calls, braces, and the modifiers that
follow them, and it stops being confident as soon as the source leaves
that shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ViewNode:
    kind: str
    text: str = ""
    children: list["ViewNode"] = field(default_factory=list)
    # modifier bag. Unknown modifiers are listed, not invented.
    font_size: float = 17
    color: str = "#111111"
    background: str | None = None
    pad_top: float = 0
    pad_right: float = 0
    pad_bottom: float = 0
    pad_left: float = 0
    corner: float = 0
    frame_height: float | None = None
    frame_max_width: bool = False
    weight: str = "regular"
    opacity: float = 1
    spacing: float = 8
    alignment: str = "center"
    notes: list[str] = field(default_factory=list)


class ParseError(Exception):
    pass


_SKIP = {
    "View", "Color", "String", "Int", "Bool", "Double", "Float", "Preview",
    "Scene", "App", "Codable", "Sendable", "Hashable", "Identifiable",
    "Observable", "Error", "Protocol",
}
# Containers and controls the preview knows how to place. Anything else with
# a call or a brace is still a view, but these win when a file has many types.
_SWIFTUI = {
    "VStack", "HStack", "ZStack", "Text", "Button", "Spacer", "Divider",
    "TextField", "SecureField", "Image", "Label", "Form", "Section", "List",
    "ScrollView", "NavigationStack", "NavigationSplitView", "Group", "GroupBox",
    "Toggle", "Picker", "Link", "ProgressView",
}


def _tokenize(source: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            i = source.find("\n", i)
            if i < 0:
                break
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch == '"':
            j = i + 1
            while j < n:
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == '"':
                    break
                j += 1
            tokens.append(("str", source[i + 1 : j].replace("\\n", "\n")))
            i = j + 1
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            tokens.append(("id", source[i:j]))
            i = j
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i + 1
            while j < n and (source[j].isdigit() or source[j] == "."):
                j += 1
            tokens.append(("num", source[i:j]))
            i = j
            continue
        if ch in "(){}[].,:@":
            tokens.append((ch, ch))
            i += 1
            continue
        i += 1
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.i = 0

    def peek(self, k: int = 0) -> tuple[str, str] | None:
        j = self.i + k
        return self.tokens[j] if j < len(self.tokens) else None

    def accept(self, kind: str, value: str | None = None) -> bool:
        tok = self.peek()
        if tok and tok[0] == kind and (value is None or tok[1] == value):
            self.i += 1
            return True
        return False

    def parse_file(self) -> ViewNode:
        bodies = []
        for idx, tok in enumerate(self.tokens):
            if tok == ("id", "body") and idx + 1 < len(self.tokens) and self.tokens[idx + 1][0] == ":":
                brace = self._brace_after(idx)
                if brace is None:
                    continue
                self.i = brace + 1
                children = self._block()
                if not children:
                    continue
                node = children[0] if len(children) == 1 else ViewNode(
                    kind="VStack", children=children, alignment="leading", spacing=8
                )
                bodies.append(node)
        if bodies:
            return max(bodies, key=_weight)
        self.i = 0
        found = self._first_view()
        if found is not None and found.kind in _SWIFTUI:
            return found
        return _fallback(self.tokens)

    def _brace_after(self, idx: int) -> int | None:
        j = idx
        while j < len(self.tokens) and self.tokens[j][0] != "{":
            j += 1
        return j if j < len(self.tokens) else None

    def _first_view(self) -> ViewNode | None:
        while self.peek():
            tok = self.peek()
            if self._at_view():
                return self._view()
            self.i += 1
        return None

    def _at_view(self) -> bool:
        tok = self.peek()
        nxt = self.peek(1)
        if not tok or tok[0] != "id" or not tok[1][:1].isupper() or tok[1] in _SKIP:
            return False
        return bool(nxt and nxt[0] in {"(", "{"})

    def _view(self) -> ViewNode:
        name = self.peek()[1]  # type: ignore[index]
        self.i += 1
        args = self._balanced("(") if self.accept("(") else ""
        children: list[ViewNode] = []
        if self.accept("{"):
            children.extend(self._block())
        # Button { } label: { Text(...) }
        while self.peek() and self.peek()[0] == "id" and self.peek(1) and self.peek(1)[0] == ":":
            self.i += 2
            if self.accept("{"):
                children.extend(self._block())
        node = ViewNode(kind=name, children=children)
        self._apply_args(node, args)
        while self.accept("."):
            self._modifier(node)
        return node

    def _block(self) -> list[ViewNode]:
        found: list[ViewNode] = []
        while self.peek() and not self.accept("}"):
            tok = self.peek()
            if self._at_view():
                found.append(self._view())
            else:
                self.i += 1
        return found

    def _balanced(self, open_ch: str) -> str:
        close = { "(": ")", "{": "}" }[open_ch]
        depth = 1
        start = self.i
        while self.peek() and depth:
            tok = self.peek()
            self.i += 1
            if tok and tok[0] == open_ch:
                depth += 1
            elif tok and tok[0] == close:
                depth -= 1
        chunk = []
        for kind, value in self.tokens[start : self.i - 1]:
            chunk.append(value if kind != "str" else f'"{value}"')
        return " ".join(chunk)

    def _apply_args(self, node: ViewNode, args: str) -> None:
        if node.kind in {"Text", "Button", "TextField", "SecureField", "Label"}:
            quoted = _first_string(args)
            if quoted:
                node.text = quoted
        if "spacing" in args:
            number = _named_number(args, "spacing")
            if number is not None:
                node.spacing = number
        if ".leading" in args:
            node.alignment = "leading"
        elif ".trailing" in args:
            node.alignment = "trailing"

    def _modifier(self, node: ViewNode) -> None:
        tok = self.peek()
        if not tok or tok[0] != "id":
            return
        name = tok[1]
        self.i += 1
        args = self._balanced("(") if self.accept("(") else ""
        if name == "font":
            size = _named_number(args, "size")
            if size:
                node.font_size = size
            if "semibold" in args or "bold" in args:
                node.weight = "bold"
        elif name == "foregroundColor" or name == "foregroundStyle":
            node.color = _color(args) or node.color
            opacity = _named_number(args, "opacity")
            if opacity is not None:
                node.opacity = opacity
        elif name == "background":
            node.background = _color(args) or "#222222"
        elif name == "padding":
            _padding(node, args)
        elif name == "cornerRadius":
            number = _first_number(args)
            if number is not None:
                node.corner = number
        elif name == "frame":
            height = _named_number(args, "height")
            if height:
                node.frame_height = height
            if "infinity" in args:
                node.frame_max_width = True
        else:
            node.notes.append(name)


def _first_string(args: str) -> str:
    if '"' not in args:
        return ""
    start = args.find('"') + 1
    end = args.find('"', start)
    return args[start:end] if end > start else ""


def _first_number(args: str) -> float | None:
    token = ""
    for ch in args:
        if ch.isdigit() or ch == ".":
            token += ch
        elif token:
            break
    try:
        return float(token) if token else None
    except ValueError:
        return None


def _named_number(args: str, name: str) -> float | None:
    at = args.find(name)
    if at < 0:
        return _first_number(args) if name == "size" else None
    return _first_number(args[at + len(name) :])


def _color(args: str) -> str | None:
    if ".white" in args:
        return "#ffffff"
    if ".black" in args:
        return "#000000"
    if "red" in args and "green" in args and "blue" in args:
        red = _named_number(args, "red") or 0
        green = _named_number(args, "green") or 0
        blue = _named_number(args, "blue") or 0
        return "#{:02x}{:02x}{:02x}".format(int(red * 255), int(green * 255), int(blue * 255))
    return None


def _padding(node: ViewNode, args: str) -> None:
    amount = _first_number(args)
    if amount is None:
        amount = 16
    edge = "all"
    for name in ("top", "bottom", "leading", "trailing", "horizontal", "vertical"):
        if f".{name}" in args:
            edge = name
            break
    if edge in {"all", "top", "vertical"}:
        node.pad_top += amount
    if edge in {"all", "bottom", "vertical"}:
        node.pad_bottom += amount
    if edge in {"all", "leading", "horizontal"}:
        node.pad_left += amount
    if edge in {"all", "trailing", "horizontal"}:
        node.pad_right += amount


def _weight(node: ViewNode) -> tuple[int, int]:
    known = 1 if node.kind in _SWIFTUI else 0
    count = 1 + sum(_weight(child)[1] for child in node.children)
    return known, count


def _fallback(tokens: list[tuple[str, str]]) -> ViewNode:
    """A file with no view body still gets a phone, not a parser error."""
    strings = [value for kind, value in tokens if kind == "str" and value.strip()]
    title = next((value for kind, value in tokens if kind == "id" and value[:1].isupper()), "Swift")
    children = [ViewNode(kind="Text", text=title, font_size=22, color="#ffffff", weight="bold")]
    for value in strings[:6]:
        children.append(ViewNode(kind="Text", text=value, font_size=14, color="#ffffff"))
    if len(children) == 1:
        children.append(ViewNode(
            kind="Text",
            text="This file has no view body yet.",
            font_size=13,
            color="#ffffff",
            opacity=0.6,
        ))
    return ViewNode(kind="VStack", children=children, alignment="leading", spacing=10, background="#000000")


def parse_swiftui(source: str) -> ViewNode:
    parser = _Parser(_tokenize(source))
    return parser.parse_file()
