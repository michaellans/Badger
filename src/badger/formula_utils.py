import re
import ast
import math
import statistics
from typing import Set, Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)

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
    """
    Validates a formula expression for safe evaluation.
    Adapted from https://github.com/slaclab/trace/blob/main/trace/utilities/formula_validation.py#L28

    This function parses the expression using Python's AST and validates that:
    - Only allowed operators and functions are used
    - All variable names are in the allowed symbols set
    - The expression is syntactically valid

    Parameters
    ----------
    expr : str
        The mathematical expression to validate
    allowed_symbols : Set[str]
        Set of allowed variable names in the expression

    Raises:
        ValueError: If the expression contains:
            - Disallowed AST node types or operators
            - Lists/tuples with complex nested expressions (only simple values allowed)
            - Lists/tuples exceeding 50 elements
            - Function calls to non-allowed functions
            - References to undefined symbols (not in allowed_symbols or allowed functions)
        SyntaxError: If the expression cannot be parsed as valid Python.
    """
    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f'Operator "{type(node).__name__}" not allowed')

        if isinstance(node, (ast.List, ast.Tuple)):
            for element in node.elts:
                if not isinstance(
                    element, (ast.Name, ast.Constant, ast.BinOp, ast.Call)
                ):
                    raise ValueError(
                        f"Lists/tuples can only contain simple values, not {type(element).__name__}"
                    )

            if len(node.elts) > 50:  # arbitrary
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


VAR = re.compile(r"`([^`]+)`")  # find backticked `var` tokens


def expanded_formula_mapping(
    data: dict,
) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """
    Provide a forward and reverse mapping for formula names to expanded formula strings in terms of
    environment variables. Non-formulas will map to themselves. Also returns a list of base_variables
    within the formulas.

    Note this generally functions well in my testing, but may have a few bugs and would
    probably be better to rewrite to use dfs dict traversal rather than recusion

    Variable substitution rules
    ---------------------------
    Substitutes variables marked with backticks. If the backticked name is present in
    "variable_mapping", recursively expands the mapped formula.

    Otherwise, it's treated as a leaf node/base observable if:
    - the name is not in node["variable_mapping"]
    - the mapping value is falsy (None, "")

    Parameters
    ----------
    - data: dict
        Badger routine "data"
        Note: this probably doesn't need the full data dict, only
        data["vocs"] and data["formulas"] if present

    Returns
    -------
    - forward: Dict[str, str]
        Mapping from each output name to either its expanded formula string (for formulas)
        or to itself (for base observables/non-formulas).
    - reverse: Dict[str, str]
        Reverse lookup mapping from expanded formula string (or identity name)
        to the first corresponding key in forward
    - base_observables: List[str]
        Names of leaf/base observables referenced during expansion within formulas

    Additional Notes
    ----------------
    - caches expanded names to avoid expanding the same named formula multiple times.
    - Detects circular references using stack (may have bug)

    """
    cache: Dict[str, str] = {}
    stack = set()

    formulas = data.get("formulas", {}) or {}

    output_names = list(data["vocs"].output_names)
    selected_formulas = {
        sel_name: formulas[sel_name]
        for sel_name in output_names
        if sel_name in formulas
    }
    base_observables = []  # keep trach of observables within formulas
    logger.debug(f"start expanding formulas: {selected_formulas}")

    def expand_node(node: Dict[str, Any]) -> str:
        logger.debug(f"expanding node: {node}")
        s = node["formula_str"]
        mapping = node.get("variable_mapping") or {}

        def sub(m: re.Match) -> str:
            var = m.group(1)
            if var not in mapping:
                base_observables.append(var)
                return f"`{var}`"  # treat as base variable
                # raise KeyError(f"Missing mapping for `{var}` in formula: {s!r}")
            target = mapping[var]
            if not target:  # base variable
                base_observables.append(var)
                return f"`{var}`"
            return f"({expand_node(target)})"

        return VAR.sub(sub, s)

    def expand_name(name: str) -> str:
        if name in cache:
            # If it has already been expanded, use the cached version
            return cache[name]
        if name in stack:
            # Don't allow circular formulas!
            raise ValueError(f"Cycle detected while expanding {name!r}")
        if name not in formulas:
            raise KeyError(f"Unknown formula name: {name!r}")

        stack.add(name)
        out = expand_node(selected_formulas[name])
        stack.remove(name)
        cache[name] = out

        return out

    forward = {}

    for name in selected_formulas:
        if not selected_formulas[name]["formula_str"]:
            # if no formula_str treat it as not a formula and map to itself.
            forward[name] = name
            continue
        expanded_name = expand_name(name)
        forward[name] = expanded_name

    for output_name in output_names:
        if output_name not in formulas:
            # it is not a formula, should map to itself
            forward[output_name] = output_name

    for obs_name in base_observables:
        if obs_name not in forward:
            forward[obs_name] = obs_name

    reverse: Dict[str, str] = {}
    for name, expanded in forward.items():
        reverse.setdefault(expanded, name)

    return forward, reverse, base_observables


def stat_key_from_expr(expr: str) -> str:
    # Extract statistic key from an expression like
    # "std(`PV1`)/mean(`PV1`)" or "percentile(`PV1`, 90)"

    # use string parsing to find what the stat function is
    s = re.sub(r"\s+", "", expr)

    ident = r"`[^`]+`"  # content with atleast 1 character inside backticks

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
