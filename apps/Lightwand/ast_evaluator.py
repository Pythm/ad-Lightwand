""" Restricted evaluator for the condition / constraint strings in the Lightwand YAML.

What it does
    The expression is parsed with ``ast.parse(mode='eval')`` and evaluated by
    walking the tree. User text is never passed to ``eval``, ``exec`` or
    ``compile``. Parsed and validated trees are cached per expression string.

What is allowed
    * ``and`` / ``or`` (short-circuit, return the operand like Python), ``not``,
      unary ``-`` / ``+``, ``+ - * / // %`` (no ``**``), comparisons
      ``== != < <= > >= in not in is is not`` (chained), ``x if c else y``.
    * Constants (str, int, float, bool, None) and tuple / list / set / dict literals.
    * Names: ``self`` (the context object) and the builtins
      float, int, str, bool, len, abs, min, max, round.
    * Attribute reads on any value, except attributes starting with ``_``.
    * Subscripts on dict / list / tuple / str with int or str keys or simple slices.
    * Calls of the builtins above, of methods on ``self`` or ``self.ADapi``
      whose name starts with a read-only prefix (``get_``, ``now_is_between``,
      ``sun_up``, ...), and of a short list of methods on str / dict /
      date / time values.

What is rejected
    lambda, comprehensions, f-strings, walrus, await, star-args, ``**kwargs``,
    ``**`` power, any other name, any other call (``call_service``,
    ``turn_on``, ``run_in``, ``listen_*``, ``fire_event``, ``set_state``, ...),
    method references without a call, expressions longer than
    ``MAX_EXPRESSION_LENGTH`` or with more than ``MAX_NODES`` nodes or deeper
    than ``MAX_DEPTH``.

What it does not guarantee
    It is a guard against mistakes and the obvious escapes, not a sandbox for
    hostile input. Allowed attribute reads and allowed ``get_...`` methods run
    real code on real objects (properties, AppDaemon API methods), and those
    can be slow or return objects whose attributes can be read. The YAML is
    written by the owner of the installation and should be treated as such.
"""
import ast
import datetime as _dt
import functools
import operator
from typing import Any, Callable, Dict

MAX_EXPRESSION_LENGTH = 1000
MAX_NODES = 200
MAX_DEPTH = 30
MAX_SEQUENCE_REPEAT = 10000

_BUILTINS: Dict[str, Callable] = {
    'float': float,
    'int': int,
    'str': str,
    'bool': bool,
    'len': len,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
}

# Methods on ``self`` / ``self.ADapi`` that may be called. Read-only by name.
_ALLOWED_CALL_PREFIXES = (
    'get_', 'now_is_between', 'sun_up', 'sun_down', 'sunrise', 'sunset',
    'entity_exists', 'anyone_home', 'everyone_home', 'noone_home',
    'is_', 'time', 'date', 'datetime', 'parse_',
)

_STR_METHODS = frozenset({
    'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'startswith', 'endswith',
    'casefold', 'split', 'isdigit', 'isnumeric', 'isalpha', 'title', 'capitalize',
})
_DICT_METHODS = frozenset({'get', 'keys', 'values', 'items'})
_DATE_METHODS = frozenset({'weekday', 'isoweekday', 'date', 'time', 'isoformat', 'timestamp'})

_BIN_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
}

_UNARY_OPS = {
    ast.Not:  operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_COMPARE_OPS = {
    ast.Eq:    operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt:    operator.lt,
    ast.LtE:   operator.le,
    ast.Gt:    operator.gt,
    ast.GtE:   operator.ge,
    ast.In:    lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is:    operator.is_,
    ast.IsNot: operator.is_not,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.BinOp, ast.Compare,
    ast.IfExp, ast.Constant, ast.Tuple, ast.List, ast.Set, ast.Dict, ast.Name, ast.Load,
    ast.Attribute, ast.Subscript, ast.Slice, ast.Call, ast.keyword,
) + tuple(_BIN_OPS) + tuple(_UNARY_OPS) + tuple(_COMPARE_OPS)


def _allowed_method_name(name: str) -> bool:
    return (
        name.startswith(_ALLOWED_CALL_PREFIXES)
        or name in _STR_METHODS
        or name in _DICT_METHODS
        or name in _DATE_METHODS
    )


def _validate(tree: ast.Expression) -> None:
    """ Reject everything that is not on the allow list. Runs once per expression. """

    count = 0
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise ValueError(f"Expression has more than {MAX_NODES} elements")
        if depth > MAX_DEPTH:
            raise ValueError(f"Expression is nested deeper than {MAX_DEPTH}")
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Unsupported expression element: {type(node).__name__}")

        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (str, int, float, bool, type(None))):
                raise ValueError(f"Unsupported constant: {node.value!r}")
        elif isinstance(node, ast.Name):
            if node.id != 'self' and node.id not in _BUILTINS:
                raise NameError(f"Unknown name '{node.id}'. Only 'self' and {', '.join(_BUILTINS)} are available")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith('_'):
                raise ValueError(f"Access to '{node.attr}' is not allowed")
        elif isinstance(node, ast.keyword):
            if node.arg is None:
                raise ValueError("Keyword unpacking (**) is not allowed")
        elif isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise ValueError("Dict unpacking (**) is not allowed")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id not in _BUILTINS:
                    raise ValueError(f"Call to '{func.id}' is not allowed")
            elif isinstance(func, ast.Attribute):
                if not _allowed_method_name(func.attr):
                    raise ValueError(f"Call to '{func.attr}' is not allowed (only read-only methods)")
            else:
                raise ValueError("Only calls to named functions or methods are allowed")

        for child in ast.iter_child_nodes(node):
            stack.append((child, depth + 1))


@functools.lru_cache(maxsize=512)
def _compile(expr: str) -> ast.Expression:
    """ Parse and validate *expr*. Cached per expression string. """

    if len(expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Expression is longer than {MAX_EXPRESSION_LENGTH} characters")
    tree = ast.parse(expr.strip(), mode='eval')
    _validate(tree)
    return tree


class SafeEval:
    """ Evaluates a tree validated by ``_compile`` with a given context. """

    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.ctx_self = context.get('self')
        self.ctx_api = getattr(self.ctx_self, 'ADapi', None)

    def value(self, node) -> Any:
        """ Evaluate *node* as a value. Functions and classes may only be called, not passed around. """

        result = self.visit(node)
        if callable(result) or isinstance(result, type):
            raise ValueError("Functions and methods must be called, they can not be used as values")
        return result

    def visit(self, node) -> Any:
        if isinstance(node, ast.Expression):
            return self.value(node.body)

        if isinstance(node, ast.BoolOp):
            result = None
            for v in node.values:
                result = self.value(v)
                if isinstance(node.op, ast.And) and not result:
                    return result
                if isinstance(node.op, ast.Or) and result:
                    return result
            return result

        if isinstance(node, ast.UnaryOp):
            return _UNARY_OPS[type(node.op)](self.value(node.operand))

        if isinstance(node, ast.BinOp):
            left = self.value(node.left)
            right = self.value(node.right)
            if isinstance(node.op, ast.Mult):
                for seq, times in ((left, right), (right, left)):
                    if isinstance(seq, (str, list, tuple)) and isinstance(times, int):
                        if len(seq) * times > MAX_SEQUENCE_REPEAT:
                            raise ValueError("Sequence repetition is too large")
            if isinstance(node.op, ast.Mod) and isinstance(left, (str, bytes)):
                raise ValueError("String formatting with % is not allowed")
            return _BIN_OPS[type(node.op)](left, right)

        if isinstance(node, ast.Compare):
            left = self.value(node.left)
            result = True
            for op, right_node in zip(node.ops, node.comparators):
                right = self.value(right_node)
                result = _COMPARE_OPS[type(op)](left, right)
                if not result:
                    return result
                left = right
            return result

        if isinstance(node, ast.IfExp):
            if self.value(node.test):
                return self.value(node.body)
            return self.value(node.orelse)

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Tuple):
            return tuple(self.value(e) for e in node.elts)
        if isinstance(node, ast.List):
            return [self.value(e) for e in node.elts]
        if isinstance(node, ast.Set):
            return {self.value(e) for e in node.elts}
        if isinstance(node, ast.Dict):
            return {self.value(k): self.value(v) for k, v in zip(node.keys, node.values)}

        if isinstance(node, ast.Name):
            if node.id == 'self':
                return self.ctx_self
            return _BUILTINS[node.id]

        if isinstance(node, ast.Attribute):
            return getattr(self.value(node.value), node.attr)

        if isinstance(node, ast.Subscript):
            container = self.value(node.value)
            if not isinstance(container, (dict, list, tuple, str)):
                raise ValueError(f"Subscript is only allowed on dict, list, tuple and str, not {type(container).__name__}")
            if isinstance(node.slice, ast.Slice):
                parts = [None if p is None else self.value(p) for p in (node.slice.lower, node.slice.upper, node.slice.step)]
                if any(p is not None and not isinstance(p, int) for p in parts):
                    raise ValueError("Slice bounds must be integers")
                return container[slice(*parts)]
            key = self.value(node.slice)
            if not isinstance(key, (int, str)):
                raise ValueError("Subscript keys must be int or str")
            return container[key]

        if isinstance(node, ast.Call):
            func = self._resolve_callee(node.func)
            args = [self.value(arg) for arg in node.args]
            kwargs = {kw.arg: self.value(kw.value) for kw in node.keywords}
            return func(*args, **kwargs)

        raise ValueError(f"Unsupported expression element: {type(node).__name__}")

    def _resolve_callee(self, func_node) -> Callable:
        if isinstance(func_node, ast.Name):
            return _BUILTINS[func_node.id]

        name = func_node.attr
        receiver = self.value(func_node.value)
        if (
            (receiver is self.ctx_self or (self.ctx_api is not None and receiver is self.ctx_api))
            and name.startswith(_ALLOWED_CALL_PREFIXES)
        ):
            return getattr(receiver, name)
        if isinstance(receiver, str) and name in _STR_METHODS:
            return getattr(receiver, name)
        if isinstance(receiver, dict) and name in _DICT_METHODS:
            return getattr(receiver, name)
        if isinstance(receiver, (_dt.date, _dt.time)) and name in _DATE_METHODS:
            return getattr(receiver, name)
        raise ValueError(f"Call to '{name}' on {type(receiver).__name__} is not allowed")


def safe_eval(expr: str, context: Dict[str, Any]) -> Any:
    """ Evaluate *expr* with *context* (``{'self': obj}``) and return the value.
    ``None`` evaluates to True. Raises for unsupported or blocked expressions. """

    if expr is None:
        return True
    if not isinstance(expr, str):
        raise ValueError(f"Condition must be a string, got {type(expr).__name__}")
    return SafeEval(context).visit(_compile(expr))


_warned: set = set()

def safe_eval_logged(owner_key: str, expr: str, context: Dict[str, Any], log: Callable) -> Any:
    """ Like ``safe_eval`` but a failing expression counts as False. The reason is
    logged at WARNING once per (owner_key, expr). """

    try:
        return safe_eval(expr, context)
    except Exception as exc:
        key = (owner_key, expr)
        if key not in _warned:
            _warned.add(key)
            log(
                f"Condition {expr!r} for {owner_key} failed and counts as false: {type(exc).__name__}: {exc}",
                level = 'WARNING'
            )
        return False
