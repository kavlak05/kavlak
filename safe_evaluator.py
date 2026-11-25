import ast
import logging
import operator as op
from typing import Union

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("NEXUS_CORE")

ALLOWED_BIN_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
}

ALLOWED_UNARY_OPS = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY_OPS:
        return ALLOWED_UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError("Sıfıra bölme hatası")
        return ALLOWED_BIN_OPS[type(node.op)](left, right)
    raise ValueError("Desteklenmeyen veya güvensiz matematiksel ifade")


def safe_evaluate(expression: str) -> Union[float, int]:
    """Matematiksel ifadeleri AST üzerinden güvenli şekilde değerlendirir."""
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(parsed)
        logger.info("İfade değerlendirildi: '%s' -> %s", expression.strip(), result)
        return result
    except Exception as exc:
        logger.warning("İfade reddedildi ('%s'): %s", expression.strip(), exc)
        raise
