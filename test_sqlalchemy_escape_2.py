from sqlalchemy import select, column, table, String
t = table("content", column("title", String))
search = "hello%world"
stmt = select(t).where(t.c.title.ilike(f"%{search}%"))
print(stmt)
