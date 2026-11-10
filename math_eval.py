"""
Safe and fast math evaluator and unit converter for macOS Spotlight clone.
"""
import ast
import math
import re
from typing import Optional, Tuple

SAFE_NAMES = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'sqrt': math.sqrt,
    'cbrt': getattr(math, 'cbrt', lambda x: x ** (1/3)),
    'log': math.log,
    'log10': math.log10,
    'log2': math.log2,
    'exp': math.exp,
    'abs': abs,
    'ceil': math.ceil,
    'floor': math.floor,
    'round': round,
    'radians': math.radians,
    'degrees': math.degrees,
    'pi': math.pi,
    'e': math.e,
}

UNITS_CONVERSION = {
    # Length (base: meter)
    ('km', 'miles'): 0.621371,
    ('miles', 'km'): 1.60934,
    ('mi', 'km'): 1.60934,
    ('km', 'mi'): 0.621371,
    ('m', 'ft'): 3.28084,
    ('ft', 'm'): 0.3048,
    ('m', 'feet'): 3.28084,
    ('feet', 'm'): 0.3048,
    ('cm', 'inch'): 0.393701,
    ('inch', 'cm'): 2.54,
    ('in', 'cm'): 2.54,
    ('cm', 'in'): 0.393701,
    ('cm', 'mm'): 10.0,
    ('mm', 'cm'): 0.1,
    ('m', 'km'): 0.001,
    ('km', 'm'): 1000.0,

    # Weight (base: kg)
    ('kg', 'lbs'): 2.20462,
    ('lbs', 'kg'): 0.453592,
    ('kg', 'pounds'): 2.20462,
    ('pounds', 'kg'): 0.453592,
    ('g', 'oz'): 0.035274,
    ('oz', 'g'): 28.3495,
    ('kg', 'g'): 1000.0,
    ('g', 'kg'): 0.001,

    # Digital data (base: megabytes)
    ('mb', 'gb'): 1 / 1024,
    ('gb', 'mb'): 1024,
    ('gb', 'tb'): 1 / 1024,
    ('tb', 'gb'): 1024,
    ('kb', 'mb'): 1 / 1024,
    ('mb', 'kb'): 1024,
    ('bytes', 'kb'): 1 / 1024,
    ('kb', 'bytes'): 1024,
}

def evaluate_ast(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError("Non-numeric constant")
    elif isinstance(node, ast.BinOp):
        left = evaluate_ast(node.left)
        right = evaluate_ast(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            return left // right
        elif isinstance(node.op, ast.Mod):
            return left % right
        elif isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                raise ValueError("Exponent too large")
            return left ** right
        raise ValueError(f"Unsupported binary operator: {type(node.op)}")
    elif isinstance(node, ast.UnaryOp):
        operand = evaluate_ast(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in SAFE_NAMES:
                func = SAFE_NAMES[func_name]
                args = [evaluate_ast(arg) for arg in node.args]
                return func(*args)
        raise ValueError("Unsupported function call")
    elif isinstance(node, ast.Name):
        if node.id in SAFE_NAMES:
            return SAFE_NAMES[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    else:
        raise ValueError(f"Unsupported syntax: {type(node)}")

def try_unit_conversion(query: str) -> Optional[Tuple[str, str]]:
    """Check for unit conversion like '100 km to miles' or '32 f to c'."""
    pattern = r'^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)\s+(?:to|in)\s+([a-zA-Z]+)\s*$'
    m = re.match(pattern, query.strip().lower())
    if not m:
        return None
    val_str, unit_from, unit_to = m.groups()
    val = float(val_str)

    # Temperature
    if (unit_from in ('f', 'fahrenheit')) and (unit_to in ('c', 'celsius')):
        res = (val - 32) * 5 / 9
        return f"{val:g} °F = {res:.2f} °C", f"{res:.2f} °C"
    if (unit_from in ('c', 'celsius')) and (unit_to in ('f', 'fahrenheit')):
        res = (val * 9 / 5) + 32
        return f"{val:g} °C = {res:.2f} °F", f"{res:.2f} °F"
    if (unit_from in ('c', 'celsius')) and (unit_to in ('k', 'kelvin')):
        res = val + 273.15
        return f"{val:g} °C = {res:.2f} K", f"{res:.2f} K"

    key = (unit_from, unit_to)
    if key in UNITS_CONVERSION:
        rate = UNITS_CONVERSION[key]
        res = val * rate
        # formatting
        if res == int(res):
            res_str = f"{int(res):,}"
        elif abs(res) < 0.01 or abs(res) > 10000:
            res_str = f"{res:.4g}"
        else:
            res_str = f"{res:,.3f}".rstrip('0').rstrip('.')
        return f"{val_str} {unit_from} = {res_str} {unit_to}", f"{res_str} {unit_to}"

    return None

def format_number(val) -> str:
    if isinstance(val, float):
        if val.is_integer():
            return f"{int(val):,}"
        if abs(val) < 1e-4 or abs(val) >= 1e12:
            return f"{val:.6g}"
        return f"{val:,.6f}".rstrip('0').rstrip('.')
    elif isinstance(val, int):
        return f"{val:,}"
    return str(val)

def evaluate_expression(query: str) -> Optional[Tuple[str, str]]:
    """
    Returns (expression_display, result_display) or None if not an expression.
    """
    raw = query.strip()
    if not raw:
        return None

    # Check unit conversion first
    unit_res = try_unit_conversion(raw)
    if unit_res:
        return unit_res

    # Quick check: does it look like math?
    # Hex or Binary conversion
    hex_m = re.match(r'^(0x[0-9a-fA-F]+)\s*(?:to\s*dec|in\s*dec)?$', raw)
    if hex_m:
        try:
            val = int(hex_m.group(1), 16)
            return raw, f"{val:,}"
        except Exception:
            pass

    bin_m = re.match(r'^(0b[01]+)\s*(?:to\s*dec|in\s*dec)?$', raw)
    if bin_m:
        try:
            val = int(bin_m.group(1), 2)
            return raw, f"{val:,}"
        except Exception:
            pass

    dec_to_hex = re.match(r'^([0-9]+)\s+(?:to|in)\s+hex$', raw.lower())
    if dec_to_hex:
        val = int(dec_to_hex.group(1))
        return raw, f"{hex(val)}"

    dec_to_bin = re.match(r'^([0-9]+)\s+(?:to|in)\s+bin$', raw.lower())
    if dec_to_bin:
        val = int(dec_to_bin.group(1))
        return raw, f"{bin(val)}"

    # Percentage operations: e.g. "15% of 200", "200 + 15%", "200 - 10%"
    pct_of = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*%\s*of\s*([0-9]+(?:\.[0-9]+)?)$', raw.lower())
    if pct_of:
        pct = float(pct_of.group(1))
        base = float(pct_of.group(2))
        res = (pct / 100.0) * base
        return f"{pct}% of {base}", format_number(res)

    pct_add_sub = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*([\+\-])\s*([0-9]+(?:\.[0-9]+)?)\s*%$', raw.lower())
    if pct_add_sub:
        base = float(pct_add_sub.group(1))
        op = pct_add_sub.group(2)
        pct = float(pct_add_sub.group(3))
        diff = (pct / 100.0) * base
        res = base + diff if op == '+' else base - diff
        return f"{base} {op} {pct}%", format_number(res)

    # General math normalization
    expr = raw
    # replace ^ with ** for power
    expr = expr.replace('^', '**')
    # replace 'x' or '×' between numbers with *
    expr = re.sub(r'(\d)\s*[xX×]\s*(\d)', r'\1 * \2', expr)
    expr = expr.replace('÷', '/')

    # Only attempt math if it contains at least one operator or known function or is a number calculation
    has_operator = any(c in expr for c in ['+', '-', '*', '/', '%', '**'])
    has_func = any(fn in expr.lower() for fn in ['sqrt', 'sin', 'cos', 'tan', 'log', 'abs', 'pi', 'e'])

    if not (has_operator or has_func):
        return None

    # Don't evaluate plain letters or command lines
    if re.search(r'[A-Za-z_]{4,}', expr) and not has_func:
        return None

    try:
        parsed = ast.parse(expr, mode='eval')
        val = evaluate_ast(parsed.body)
        formatted = format_number(val)
        return raw, formatted
    except Exception:
        return None
