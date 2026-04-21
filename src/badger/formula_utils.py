import re
import ast
import math
import statistics
import numpy as np
from typing import Set, Dict, Any, Tuple

_ALLOWED_FUNC_NAMES: set[str] = {
    *vars(math),
    *vars(statistics),
    *vars(np),
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.Constant,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.BitXor,
)


def validate_formula(expr: str, allowed_symbols: Set[str]) -> None:
    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f'Operator "{type(node).__name__}" not allowed')

        if isinstance(node, ast.Call):
            fn = node.func.id if isinstance(node.func, ast.Name) else None
            if fn not in _ALLOWED_FUNC_NAMES:
                raise ValueError(f'Function "{fn}" not permitted')

        if isinstance(node, ast.Name):
            if node.id not in allowed_symbols and node.id not in _ALLOWED_FUNC_NAMES:
                raise ValueError(f'Unknown symbol "{node.id}"')


def sanitize_for_validation(expr: str) -> tuple[str, set[str]]:
    """Replace backtick-quoted variables like `PV1` with temp identifiers (v0, v1, ...).

    Returns (python_expr, allowed_syms). `allowed_syms` should be passed to validate_formula.
    """
    mapping: dict[str, str] = {}

    def _repl(match: re.Match) -> str:
        var = match.group(1)
        if var not in mapping:
            mapping[var] = f"v{len(mapping)}"
        return mapping[var]

    # Match `...` (no backticks inside); preserve everything else unchanged
    python_expr = re.sub(r"`([^`]+)`", _repl, expr)
    return python_expr, set(mapping.values())


VAR = re.compile(r"`([^`]+)`")  # find `var` tokens


def expanded_formula_mapping(data: dict) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Returns:
      forward: {name: expanded_formula_string}
      reverse: {expanded_formula_string: name}
    """
    cache: Dict[str, str] = {}
    stack = set()

    formulas = data.get("formulas", {}) or {}
    output_names = list(data["vocs"].output_names)
    print(f"start expanding formulas: {formulas}")

    def expand_node(node: Dict[str, Any]) -> str:
        # print(f"expand node? {node}")
        s = node["formula_str"]
        mapping = node.get("variable_mapping") or {}

        # print(f"mapping: {mapping}")
        def sub(m: re.Match) -> str:
            var = m.group(1)
            # print("SUB")
            # print(f"  var: {var}")
            if var not in mapping:
                raise KeyError(f"Missing mapping for `{var}` in formula: {s!r}")
            # print(f"  mapping: {mapping}")
            target = mapping[var]
            # print(f"  target: {mapping[var]}")
            if target is None:  # base variable
                return f"`{var}`"
            return f"({expand_node(target)})"

        return VAR.sub(sub, s)

    def expand_name(name: str) -> str:
        print(f"expand_name: {name}")
        if name in cache:
            # If it has already been expanded, use the cached version
            return cache[name]
        if name in stack:
            # Don't allow circular formulas!
            raise ValueError(f"Cycle detected while expanding {name!r}")
        if name not in formulas:
            raise KeyError(f"Unknown formula name: {name!r}")

        stack.add(name)
        # print(f"formulas: {formulas}")
        # print(f"node: {formulas[name]}")
        out = expand_node(formulas[name])
        stack.remove(name)

        cache[name] = out
        return out

    forward = {}

    for name in formulas:
        expanded_name = expand_name(name)
        forward[name] = expanded_name

    for output_name in output_names:
        if output_name not in formulas:
            # it is not a formula, should map to itself
            forward[output_name] = output_name

    reverse: Dict[str, str] = {}
    for name, expanded in forward.items():
        reverse.setdefault(expanded, name)

    return forward, reverse


def stat_key_from_expr(expr: str) -> str:
    # Currently unused
    # Extract statistic key from an expression like
    # "std(`PV1`)/mean(`PV1`)" or "percentile(`PV1`, 90)"

    # use string parsing to find what the stat function is
    s = re.sub(r"\s+", "", expr)

    ident = r"`[^`]+`"  # r"`[^`]*`"  # ANY content inside backticks (including empty)
    # If you want at least 1 char: ident = r"`[^`]+`"

    if re.fullmatch(rf"std\({ident}\)/mean\({ident}\)", s):
        return "std_rel"
    if re.fullmatch(rf"mean\({ident}\)", s):
        return "mean"
    if re.fullmatch(rf"std\({ident}\)", s):
        return "std"

    m = re.fullmatch(rf"percentile\({ident},(\d+)\)", s)
    if m:
        p = int(m.group(1))
        return "median" if p == 50 else f"p{p}"

    raise ValueError(f"Unrecognized expression: {expr!r}")
