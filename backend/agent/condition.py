"""
condition 表达式安全求值器（接口规范 §3）

用于 NPC 状态机、事件触发条件、结局判定。
基于 Python AST 模块，仅允许比较/逻辑/成员运算，拒绝非白名单节点类型。

BNF 文法见接口规范 §3.2
"""

import ast
import operator
import random
from typing import Any, Dict, Callable


# 允许的 AST 节点类型
_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BoolOp,       # and / or
    ast.Compare,      # 比较运算
    ast.UnaryOp,      # not
    ast.Name,         # 字段引用 / enum 值
    ast.Attribute,    # 嵌套字段引用 sophia.stress
    ast.Constant,     # 字面量（数字/字符串/布尔）
    ast.List,          # 列表字面量
    ast.Load,         # 加载上下文
    ast.USub,         # 负号
    ast.Not,          # not 运算
    ast.And,          # and 运算符
    ast.Or,           # or 运算符
    ast.Call,         # 白名单函数调用 (random_roll 等)
    # 比较运算符
    ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE,
    ast.Gt, ast.GtE,
    ast.In, ast.NotIn,
)

# 允许的内置函数（白名单）
_ALLOWED_FUNCS: Dict[str, Callable] = {
    "random_roll": lambda p: random.random() < float(p),
}

# 允许的比较运算符
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def evaluate_condition(expr: str, context: Dict[str, Any]) -> bool:
    """安全解析并求值 condition 表达式

    Args:
        expr: 条件表达式字符串，如 "sol >= 30 and sophia.stress >= 0.7"
        context: 上下文字典，包含可引用的字段值

    Returns:
        bool: 表达式求值结果

    Raises:
        ValueError: 表达式包含不支持的语法或未知字段
        SyntaxError: 表达式语法错误

    示例:
        >>> ctx = {"sol": 35, "sophia": {"stress": 0.8}}
        >>> evaluate_condition("sol >= 30 and sophia.stress >= 0.7", ctx)
        True
    """
    if not expr or not expr.strip():
        return True  # 空条件视为无条件通过

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SyntaxError(f"condition 表达式语法错误: {expr!r} — {e}")

    # 安全检查：拒绝非白名单节点
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            raise ValueError(
                f"condition 表达式包含不支持的语法: "
                f"{type(node).__name__} in {expr!r}"
            )

    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, context: Dict[str, Any]) -> Any:
    """递归求值 AST 节点"""

    if isinstance(node, ast.BoolOp):
        # and / or
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
        elif isinstance(node.op, ast.Or):
            result = False
            for v in values:
                result = result or v
            return result

    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, context)
        if isinstance(node.op, ast.Not):
            return not operand
        elif isinstance(node.op, ast.USub):
            return -operand

    elif isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            op_func = _COMPARE_OPS.get(type(op))
            if op_func is None:
                raise ValueError(f"不支持的比较运算符: {type(op).__name__}")
            if not op_func(left, right):
                return False
            left = right
        return True

    elif isinstance(node, ast.Name):
        # 字段引用或 enum 值
        name = node.id
        if name in context:
            return context[name]
        # 布尔字面量
        if name == "true":
            return True
        if name == "false":
            return False
        # 未知名称作为 enum 值返回（如 B, alpha, awakening）
        return name

    elif isinstance(node, ast.Attribute):
        # 嵌套字段引用 sophia.stress
        obj = _eval_node(node.value, context)
        attr = node.attr
        if isinstance(obj, dict):
            if attr in obj:
                return obj[attr]
            raise ValueError(f"字段不存在: {attr}")
        raise ValueError(f"无法对非字典对象取属性: {obj!r}")

    elif isinstance(node, ast.Constant):
        return node.value

    elif isinstance(node, ast.List):
        return [_eval_node(e, context) for e in node.elts]

    elif isinstance(node, ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        if func_name not in _ALLOWED_FUNCS:
            raise ValueError(f"不允许的函数调用: {func_name}")
        args = [_eval_node(a, context) for a in node.args]
        return _ALLOWED_FUNCS[func_name](*args)

    else:
        raise ValueError(f"不支持的 AST 节点类型: {type(node).__name__}")


# ============================================================
# 便捷函数
# ============================================================

def check_conditions(conditions: list[str], context: Dict[str, Any]) -> str:
    """按顺序评估条件列表，返回第一个匹配的索引

    用于 ending_determination（接口规范 §5）

    Args:
        conditions: 条件表达式列表
        context: 上下文字典

    Returns:
        第一个为 true 的条件索引，无匹配返回 -1
    """
    for i, cond in enumerate(conditions):
        try:
            if evaluate_condition(cond, context):
                return i
        except (ValueError, SyntaxError) as e:
            print(f"[WARN] condition 求值失败 (index={i}): {e}")
    return -1
