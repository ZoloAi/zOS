"""calculator — pure arithmetic, args -> result only (no state, no orchestration)."""


def add(num1, num2):
    a, b = float(num1), float(num2)
    result = a + b
    return f"{_fmt(a)} + {_fmt(b)} = {_fmt(result)}"


def _fmt(n):
    return int(n) if n == int(n) else n
