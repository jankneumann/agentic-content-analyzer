## 2024-03-24 - Efficient Multi-Dimensional Aggregation
**Learning:** Performing multiple independent `GROUP BY` and scalar sum queries sequentially to fetch marginal statistics (like status counts, provider counts, voice counts, and total duration) causes an N+1 query problem that degrades database performance by requiring multiple full table scans and round-trips.
**Action:** When aggregating multiple orthogonal dimensions from a single table, combine them into a single multi-dimensional `GROUP BY (col1, col2, ...)` SQLAlchemy query. Retrieve the fully grouped result set and compute the marginal statistics (1D sums) manually via a single pass in Python to significantly reduce database IOps.


## 2024-03-24 - Efficient Multi-Dimensional Aggregation
**Learning:** Performing multiple independent `GROUP BY` and scalar sum queries sequentially to fetch marginal statistics (like status counts, provider counts, voice counts, and total duration) causes an N+1 query problem that degrades database performance by requiring multiple full table scans and round-trips.
**Action:** When aggregating multiple orthogonal dimensions from a single table, combine them into a single multi-dimensional `GROUP BY (col1, col2, ...)` SQLAlchemy query. Retrieve the fully grouped result set and compute the marginal statistics (1D sums) manually via a single pass in Python to significantly reduce database IOps.

## 2025-02-13 - Optimize regex compilation and search highlighting
**Learning:** In text-heavy processing like `search.py` and `chunking.py`, compiling regexes inside loops or frequently called functions adds measurable overhead. Furthermore, for multi-term highlighting, creating a single regex using alternation (e.g. `rf"(\b(?:{term_patterns})\w*)"`) instead of iterating through terms and running `re.sub` for each term reduces the number of full-text scans from O(N) to O(1) and prevents unintended overlapping replacements (like putting `<mark>` tags inside other `<mark>` tags).
**Action:** Always pre-compile regex patterns at the module level. When highlighting or searching for multiple terms, combine them into a single regex with `|` instead of using a loop with multiple `re.sub` calls.
