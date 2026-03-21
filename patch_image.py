import re

with open("src/api/image_generation_routes.py", "r") as f:
    content = f.read()

content = content.replace(
    'raise HTTPException(status_code=422, detail=str(e))',
    'raise HTTPException(status_code=422, detail="Invalid image generator configuration")'
)

with open("src/api/image_generation_routes.py", "w") as f:
    f.write(content)

print("Patched image_generation_routes.py")
