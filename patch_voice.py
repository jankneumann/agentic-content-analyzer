import re

with open("src/api/voice_stream_routes.py", "r") as f:
    content = f.read()

content = content.replace(
    '{"type": "error", "text": str(e), "cleaned": False}',
    '{"type": "error", "text": "Provider initialization failed", "cleaned": False}'
)

content = content.replace(
    '{"type": "error", "text": f"Model configuration error: {e}", "cleaned": False}',
    '{"type": "error", "text": "Model configuration error", "cleaned": False}'
)

with open("src/api/voice_stream_routes.py", "w") as f:
    f.write(content)

print("Patched voice_stream_routes.py")
