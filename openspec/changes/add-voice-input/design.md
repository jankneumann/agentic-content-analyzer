## Context

The application has a mature TTS pipeline (speech *output* via OpenAI/ElevenLabs) and a settings management system with 3-tier precedence (env → db → default). The frontend is a React/TanStack Router SPA with Radix UI components, running as a PWA. Users currently interact via keyboard only — chat, search, URL input. Mobile users on the PWA would benefit significantly from voice input, and the Web Speech API provides zero-dependency browser-native speech recognition with good coverage (Chrome, Edge, Safari).

Key existing touchpoints:
- `ChatInput.tsx` — textarea with send button, auto-expand, keyboard shortcuts
- `VoiceConfigurator.tsx` — settings panel for TTS output (provider, voice, speed, presets)
- `use-settings.ts` — React Query hooks for settings CRUD
- `voice_settings_routes.py` — backend API with 3-tier resolution
- Search inputs across content list, summary view, and prompt management

## Goals / Non-Goals

**Goals:**
- Add voice-to-text input to chat, search, and URL fields using the Web Speech API
- Provide a reusable `useVoiceInput` hook and `VoiceInputButton` component
- Persist voice input preferences (language, continuous mode, auto-submit) in the existing settings system
- Show real-time interim transcripts with clear recording state
- Graceful degradation when Web Speech API is unavailable
- Provide LLM-based cleanup of raw voice transcripts into structured, polished text

**Non-Goals:**
- On-device STT engines (Whisper.cpp, Vosk) — separate proposal (`add-on-device-stt`)
- Server-side transcription — no audio uploaded to backend
- Voice commands / voice navigation (future scope)
- Multi-language simultaneous recognition
- Custom language model training

## Decisions

### 1. Web Speech API only (no third-party STT libraries)

**Choice**: Use `window.SpeechRecognition` / `window.webkitSpeechRecognition` directly.

**Alternatives considered**:
- **Whisper.js (WASM)**: Adds ~40MB download, complex build pipeline. Better suited for on-device STT proposal.
- **Cloud STT API (Google/AWS)**: Requires backend proxy, adds latency and cost. Overkill for text input.
- **react-speech-recognition**: Thin wrapper, but adds a dependency for ~50 lines of hook code.

**Rationale**: Zero dependencies. The Web Speech API is sufficient for dictation-style input. Browser support covers Chrome (70%+ market share), Edge, and Safari. Firefox lacks support but the separate `add-on-device-stt` proposal will address that gap.

### 2. Reusable hook + component pattern

**Choice**: `useVoiceInput()` hook encapsulates all SpeechRecognition logic; `VoiceInputButton` is a standalone UI component that consumes the hook.

**Rationale**: Follows the project's existing hook pattern (`use-settings.ts`, `use-content.ts`). The hook can be composed into any input field — chat, search, URL — without duplicating logic. The button component handles mic icon, pulsing animation, and ARIA labels.

### 3. Extend existing voice settings (not a new settings namespace)

**Choice**: Add voice input fields under the existing `voice.*` namespace: `voice.input_language`, `voice.input_continuous`, `voice.input_auto_submit`.

**Alternatives considered**:
- **New `voice-input.*` namespace**: Separates concerns but fragments the voice settings UI.
- **Frontend-only localStorage**: Simpler but doesn't sync across devices and breaks the established settings pattern.

**Rationale**: The VoiceConfigurator already groups voice settings. Adding an "Input" section below the existing "Output" section keeps the UI cohesive. The backend already handles arbitrary `voice.*` keys via the settings override system.

### 4. Interim transcript display inline

**Choice**: Show interim (in-progress) results directly in the target input field with a distinct visual style (lighter color, italic), replacing with the final transcript on recognition end.

**Alternatives considered**:
- **Floating overlay**: More visually distinct but adds layout complexity and can obscure content on mobile.
- **Separate transcript panel**: Too heavy for simple text input.

**Rationale**: Users expect dictated text to appear where they're typing, similar to mobile keyboard voice input. Inline display with visual differentiation (opacity/italic) for interim results is the most natural UX.

### 5. Feature detection with clear fallback messaging

**Choice**: Check `window.SpeechRecognition || window.webkitSpeechRecognition` at hook initialization. When unavailable, the mic button renders as disabled with a tooltip explaining browser support requirements.

**Rationale**: No runtime errors. Users on unsupported browsers (Firefox, older mobile browsers) see a clear explanation rather than a broken button. The `add-on-device-stt` proposal will provide a WASM-based fallback for these browsers.

### 6. LLM-based transcript cleanup via backend API

**Choice**: Add a `POST /api/v1/voice/cleanup` endpoint that accepts raw transcript text and returns structured, cleaned-up text. The frontend adds a "cleanup" button (sparkle/wand icon) next to the mic button, and supports a voice key phrase (e.g., "clean up") that triggers the cleanup automatically.

**Alternatives considered**:
- **Client-side regex/rules cleanup**: No LLM cost, but can't handle context-aware restructuring (e.g., turning "add a bullet point about uh the new API endpoint" into "- New API endpoint").
- **Always-on cleanup (every transcript)**: Adds latency and cost to every voice input, even short search queries where cleanup is unnecessary.
- **Prompt-only cleanup (no dedicated endpoint)**: Embed cleanup in the chat system prompt. But this conflates the user's intent ("clean up my text") with the chat task.

**Rationale**: An explicit cleanup step gives users control — they choose when to clean up. The backend endpoint registers `VOICE_CLEANUP` as a proper `ModelStep` in `src/config/models.py`, adds its default to `model_registry.yaml`, and wires it through `ModelConfig.__init__()` — the same pattern used by all other pipeline steps (summarization, theme_analysis, etc.). This means:
- It automatically appears in the Model Configuration section of the Settings UI
- Users can override via `MODEL_VOICE_CLEANUP` env var, DB override, or YAML default
- Cost data and model families show up in the dropdown just like other steps

The voice key phrase provides a hands-free trigger, while the button provides a visual alternative.

The cleanup prompt instructs the LLM to:
- Fix grammar, punctuation, and filler words ("um", "uh", "like")
- Structure the text appropriately (paragraphs, bullet points, code blocks) based on context
- Preserve the user's intent and meaning without adding information
- Return only the cleaned text (no explanations or metadata)

## Risks / Trade-offs

- **Browser support gap (Firefox)**: ~8% of users. → Mitigated by `add-on-device-stt` proposal providing WASM fallback. Disabled mic button with tooltip in the interim.
- **Microphone permission UX**: Browser permission prompts can be confusing. → Mitigated by showing a pre-prompt explanation before first use and handling `NotAllowedError` gracefully with a help message.
- **Accuracy varies by accent/noise**: Web Speech API quality depends on Google's cloud service. → Mitigated by showing interim results so users can see and correct in real-time. Not a blocking issue for dictation use case.
- **Privacy**: Audio is sent to Google's servers for Chrome's Web Speech API. → Documented in settings tooltip. The `add-on-device-stt` proposal provides a fully private alternative.
- **Network dependency**: Web Speech API requires internet in Chrome. → Error handling for `network` error type. Offline fallback deferred to `add-on-device-stt`.
- **LLM cleanup latency**: 1-3 seconds for API call. → Mitigated by showing a loading spinner on the cleanup button; input remains editable during cleanup.
- **LLM cleanup cost**: Each cleanup call costs tokens. → Uses configurable model (default to Haiku for cost efficiency); only triggered on explicit user action, not automatically.

## Open Questions

- Should auto-submit be on by default, or require explicit opt-in? (Leaning: opt-in, since accidental sends are worse than an extra tap.)
- Should the voice input button appear in all search inputs or only in chat? (Leaning: chat + main search bar initially, expand later based on usage.)
