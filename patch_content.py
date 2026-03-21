with open("src/api/content_routes.py", "r") as f:
    content = f.read()

content = content.replace(
    'raise HTTPException(status_code=400, detail=str(e))',
    'raise HTTPException(status_code=400, detail="Invalid merge operation")'
)

with open("src/api/content_routes.py", "w") as f:
    f.write(content)

print("Patched content_routes.py")
