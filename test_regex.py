import re

old_heading = re.compile(r"^(#{1,6})\s+(.+)$")
new_heading = re.compile(r"^(#{1,6})\s(.+)$")

tests = [
    "# A",
    "#  A",
    "#   A",
    "## A",
    "# ",
    "#  ",
    "#\tA",
    "#\t\tA"
]

for t in tests:
    m_old = old_heading.match(t)
    m_new = new_heading.match(t)
    old_res = m_old.group(2).strip() if m_old else None
    new_res = m_new.group(2).strip() if m_new else None
    print(f"{repr(t)}: old={old_res}, new={new_res}, equal={old_res == new_res}")
