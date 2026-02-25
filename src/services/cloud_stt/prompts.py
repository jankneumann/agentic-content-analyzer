"""Prompt templates for cloud STT providers."""

# Gemini transcription + cleanup prompt.
# This prompt instructs Gemini to transcribe AND clean up the audio in one pass,
# so the result is ready to use without a separate VOICE_CLEANUP step.
GEMINI_TRANSCRIPTION_CLEANUP_PROMPT = """\
Transcribe the following audio input accurately and clean up the transcript:

1. Fix grammar and punctuation
2. Remove filler words (um, uh, like, you know) unless they add meaning
3. Structure into clear sentences
4. Preserve the speaker's intent and meaning exactly
5. Do not add, remove, or rephrase substantive content
6. If the language is not English, transcribe in the original language

Return ONLY the cleaned transcript text, nothing else.\
"""
