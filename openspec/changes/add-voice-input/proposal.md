## Why

The application currently requires all user input via keyboard — chat queries, URL submissions, and search terms. Adding browser-native voice input via the Web Speech API lets users dictate content hands-free, which is especially valuable on mobile (where the app already runs as a PWA) and for accessibility. The existing TTS/audio output infrastructure handles speech *out*; this change adds speech *in*.

## What Changes

- Add a voice input button to ChatInput, search bars, and URL input fields
- Implement a `useVoiceInput` React hook wrapping the Web Speech API (SpeechRecognition)
- Add real-time interim transcript display with visual recording indicator
- Add voice input settings to the existing VoiceConfigurator (language, continuous mode, auto-submit)
- Extend the settings API to persist voice input preferences (reusing the existing env → db → default tier)
- Add a `VoiceInputButton` component with microphone icon, pulsing animation, and accessibility labels
- Provide graceful degradation for browsers without Web Speech API support (feature detection, fallback messaging)
- Add an LLM-based cleanup step that transforms raw voice transcripts into structured, polished text — triggered by a voice key phrase (e.g., "clean up") or a dedicated cleanup button next to the microphone button
- Add a backend API endpoint for LLM transcript cleanup, configurable with model selection via the existing model configuration system

## Capabilities

### New Capabilities
- `voice-input`: Browser-native speech-to-text input using the Web Speech API, including recording UI, interim transcripts, error handling, LLM-based transcript cleanup, and settings persistence

### Modified Capabilities
- `settings-management`: Add voice input preferences (language, continuous mode, auto-submit) to the settings page alongside existing voice output configuration

## Impact

- **Frontend**: New hook (`useVoiceInput`), new component (`VoiceInputButton`), modifications to `ChatInput`, search input, and `VoiceConfigurator`
- **Backend**: Voice settings routes extension, new LLM cleanup endpoint (`POST /api/v1/voice/cleanup`)
- **Dependencies**: None for STT (browser-native); LLM cleanup uses the existing Anthropic/OpenAI SDK already in the project
- **APIs**: Extended `GET/PUT/DELETE /api/v1/settings/voice` for input settings; new `POST /api/v1/voice/cleanup` for transcript cleanup
- **Accessibility**: Adds ARIA live regions for transcript feedback, keyboard-accessible mic toggle
- **Browser support**: Chrome, Edge, Safari (full); Firefox (partial — needs on-device STT fallback from separate proposal)
