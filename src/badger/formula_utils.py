import re
import ast
import math
import statistics
import numpy as np
from typing import Set, Dict, Any, Tuple

_UNSAFE_MATH_FUNCS = {
    "factorial",
    "gamma",
    "lgamma",
    "comb",
    "perm",
}

_SAFE_NUMPY_FUNCS = {
    "mean",
    "median",
    "std",
    "min",
    "max",
    "sum",
    "abs",
    "sqrt",
    "square",
    "exp",
    "log",
    "log10",
    "log2",
    "sin",
    "cos",
    "tan",
}

_SAFE_BUILTINS = {
    "abs",
    "sum",
    "min",
    "max",
    "round",
    "int",
    "float",
    "bool",
}

_ALLOWED_FUNC_NAMES: set[str] = (
    {
        name
        for name in dir(math)
        if callable(getattr(math, name))
        and not name.startswith("_")
        and name not in _UNSAFE_MATH_FUNCS
    }
    | {
        name
        for name in dir(statistics)
        if callable(getattr(statistics, name)) and not name.startswith("_")
    }
    | _SAFE_NUMPY_FUNCS
    | _SAFE_BUILTINS
    | {
        "pi",
        "e",
        "tau",
    }
)

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
    ast.List,
    ast.Tuple,
)


def validate_formula(expr: str, allowed_symbols: Set[str]) -> None:
    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f'Operator "{type(node).__name__}" not allowed')

        # Limit list/tuple size, prevent nested lists (only allow name, constant)
        if isinstance(node, (ast.List, ast.Tuple)):
            for element in node.elts:
                if not isinstance(element, (ast.Name, ast.Constant, ast.BinOp)):
                    raise ValueError(
                        f"Lists/tuples can only contain simple values, not {type(element).__name__}"
                    )

            if len(node.elts) > 50:  # arbitrary size
                raise ValueError(f"List/tuple too large: {len(node.elts)} elements")

        if isinstance(node, ast.Call):
            fn = node.func.id if isinstance(node.func, ast.Name) else None
            if fn not in _ALLOWED_FUNC_NAMES:
                raise ValueError(f'Function "{fn}" not permitted')

        if isinstance(node, ast.Name):
            if node.id not in allowed_symbols and node.id not in _ALLOWED_FUNC_NAMES:
                raise ValueError(
                    f'Unknown symbol "{node.id}". Use `backticks` around variable names'
                )


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
    base_observables = []  # keep trach of observables within formulas
    print(f"start expanding formulas: {formulas}")

    def expand_node(node: Dict[str, Any]) -> str:
        print(f"expand node? {node}")
        s = node["formula_str"]
        mapping = node.get("variable_mapping") or {}

        print(f"mapping: {mapping}")

        def sub(m: re.Match) -> str:
            var = m.group(1)
            print("SUB")
            print(f"  var: {var}")
            if var not in mapping:
                base_observables.append(var)
                return f"`{var}`"  # treat as base variable
                # raise KeyError(f"Missing mapping for `{var}` in formula: {s!r}")
            print(f"  mapping: {mapping}")
            target = mapping[var]
            print(f"  target: {mapping[var]}")
            if not target:  # base variable
                base_observables.append(var)
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
        print(f"formulas: {formulas}")
        print(f"node: {formulas[name]}")
        out = expand_node(formulas[name])
        stack.remove(name)

        cache[name] = out
        return out

    forward = {}

    for name in formulas:
        if not formulas[name]["formula_str"]:
            # using formulas to store user-added observables without formulas
            # if no formula_str treat it as not a formula for mapping.
            forward[name] = name
            continue
        expanded_name = expand_name(name)
        forward[name] = expanded_name

    for output_name in output_names:
        if output_name not in formulas:
            # it is not a formula, should map to itself
            forward[output_name] = output_name

    print(f"base_observables: {base_observables}")
    for obs_name in base_observables:
        if obs_name not in forward:
            forward[obs_name] = obs_name

    reverse: Dict[str, str] = {}
    for name, expanded in forward.items():
        reverse.setdefault(expanded, name)

    return forward, reverse, base_observables


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
