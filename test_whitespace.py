import re
import timeit

text = "  hello \t\n world   \r\n\t  test  "

def using_re(t):
    return re.sub(r"\s+", " ", t).strip()

def using_split(t):
    return " ".join(t.split())

print("RE:", repr(using_re(text)))
print("SPLIT:", repr(using_split(text)))

print("RE time:", timeit.timeit(lambda: using_re(text), number=100000))
print("SPLIT time:", timeit.timeit(lambda: using_split(text), number=100000))
