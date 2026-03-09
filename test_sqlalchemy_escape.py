from sqlalchemy import select, column, table, String
t = table("content", column("title", String))
stmt = select(t).where(t.c.title.ilike(f"%hello%"))
print(stmt)
