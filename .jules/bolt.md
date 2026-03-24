## 2024-03-24 - Efficient Multi-Dimensional Aggregation
**Learning:** Performing multiple independent `GROUP BY` and scalar sum queries sequentially to fetch marginal statistics (like status counts, provider counts, voice counts, and total duration) causes an N+1 query problem that degrades database performance by requiring multiple full table scans and round-trips.
**Action:** When aggregating multiple orthogonal dimensions from a single table, combine them into a single multi-dimensional `GROUP BY (col1, col2, ...)` SQLAlchemy query. Retrieve the fully grouped result set and compute the marginal statistics (1D sums) manually via a single pass in Python to significantly reduce database IOps.


## 2024-03-24 - Efficient Multi-Dimensional Aggregation
**Learning:** Performing multiple independent `GROUP BY` and scalar sum queries sequentially to fetch marginal statistics (like status counts, provider counts, voice counts, and total duration) causes an N+1 query problem that degrades database performance by requiring multiple full table scans and round-trips.
**Action:** When aggregating multiple orthogonal dimensions from a single table, combine them into a single multi-dimensional `GROUP BY (col1, col2, ...)` SQLAlchemy query. Retrieve the fully grouped result set and compute the marginal statistics (1D sums) manually via a single pass in Python to significantly reduce database IOps.
