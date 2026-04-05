import re
from src.utils.markdown import parse_sections

md1 = """# Title
## Section 1
- Item 1
- Item 2
## Section 2
Content here.
#
"""

sections = parse_sections(md1)
for s in sections:
    print(s.heading, s.level)
