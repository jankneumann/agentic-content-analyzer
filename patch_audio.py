import re

with open("src/api/audio_digest_routes.py", "r") as f:
    content = f.read()

content = content.replace(
    'audio_digest.error_message = str(e)',
    'audio_digest.error_message = "Audio digest generation failed due to an internal error"'
)

content = content.replace(
    'summary=str(e)[:200],',
    'summary="Audio digest generation failed due to an internal error",'
)

content = content.replace(
    '"error": str(e)[:500],',
    '"error": "Audio digest generation failed due to an internal error",'
)

with open("src/api/audio_digest_routes.py", "w") as f:
    f.write(content)

print("Patched audio_digest_routes.py")
