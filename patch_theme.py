with open("src/api/theme_routes.py", "r") as f:
    content = f.read()

content = content.replace(
    'record.error_message = str(e)[:1000]',
    'record.error_message = "Theme analysis failed due to an internal error"'
)

with open("src/api/theme_routes.py", "w") as f:
    f.write(content)

print("Patched theme_routes.py")
