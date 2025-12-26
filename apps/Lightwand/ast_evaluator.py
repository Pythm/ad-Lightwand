import ast
import operator
from typing import Any, Dict

OPERATORS = {
    ast.And:   operator.and_,
    ast.Or:    operator.or_,
    ast.Not:   operator.not_,
    ast.Eq:    operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt:    operator.lt,
    ast.LtE:   operator.le,
    ast.Gt:    operator.gt,
    ast.GtE:   operator.ge,
}

class SafeEval(ast.NodeVisitor):
    """
    Very small, safe AST evaluator.

    It accepts only the following constructs:
      * Boolean ops (and / or / not)
      * Comparisons (==, !=, <, <=, >, >=)
      * Attribute access on a known object (e.g. self.foo)
      * Function calls on that object (e.g. self.now_is_between(...))
      * Constants (int, float, str, bool, None)
    """

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def visit(self, node):
        # The root of an eval‑mode AST is an `Expression`
        if isinstance(node, ast.Expression):
            return self.visit(node.body)

        if isinstance(node, ast.Module):
            # Not expected for `mode='eval'`, but keeps compatibility
            return self.visit(node.body[0])

        if isinstance(node, ast.Expr):
            return self.visit(node.value)

        # Boolean ops
        if isinstance(node, ast.BoolOp):
            op_func = OPERATORS[type(node.op)]
            values = [self.visit(v) for v in node.values]
            result = values[0]
            for v in values[1:]:
                result = op_func(result, v)
            return result

        # Unary ops – only `not`
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self.visit(node.operand)

        # Comparisons
        if isinstance(node, ast.Compare):
            left = self.visit(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = self.visit(right_node)
                op_func = OPERATORS[type(op)]
                if not op_func(left, right):
                    return False
                left = right
            return True

        # Attribute access (self.foo)
        if isinstance(node, ast.Attribute):
            value = self.visit(node.value)
            return getattr(value, node.attr)

        # Name (e.g. self)
        if isinstance(node, ast.Name):
            if node.id in self.context:
                return self.context[node.id]
            raise NameError(f"Unknown variable '{node.id}'")

        # Call (func(args))
        if isinstance(node, ast.Call):
            func = self.visit(node.func)
            args = [self.visit(arg) for arg in node.args]
            kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
            return func(*args, **kwargs)

        # Constant (int, float, str, bool, None)
        if isinstance(node, ast.Constant):
            return node.value

        raise ValueError(f"Unsupported expression element: {type(node).__name__}")

def safe_eval(expr: str, context: Dict[str, Any]) -> Any:
    """ Parse *expr* once (AST) and evaluate it with *context*.
    Raises ValueError for any unsupported syntax. """
    if expr is None:
        return True
    tree = ast.parse(expr, mode="eval")
    return SafeEval(context).visit(tree)