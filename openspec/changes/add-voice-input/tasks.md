## 1. Voice Input Hook

- [ ] 1.1 Create `web/src/hooks/use-voice-input.ts` with `useVoiceInput` hook wrapping SpeechRecognition API
- [ ] 1.2 Implement feature detection (`isSupported`) for `SpeechRecognition` / `webkitSpeechRecognition`
- [ ] 1.3 Implement `startListening`, `stopListening`, `toggleListening` control methods
- [ ] 1.4 Implement interim transcript (`interimTranscript`) and final transcript (`transcript`) state
- [ ] 1.5 Implement `continuous` mode and `lang` configuration options
- [ ] 1.6 Implement `resetTranscript` method
- [ ] 1.7 Handle all SpeechRecognition error events (`not-allowed`, `no-speech`, `network`, `audio-capture`) with user-facing messages

## 2. Voice Input Button Component

- [ ] 2.1 Create `web/src/components/voice/VoiceInputButton.tsx` with microphone icon (Lucide `Mic` / `MicOff`)
- [ ] 2.2 Implement idle state (mic icon, `aria-label="Start voice input"`)
- [ ] 2.3 Implement recording state (pulsing red ring animation, `aria-label="Stop voice input"`)
- [ ] 2.4 Implement disabled state (`aria-disabled="true"`, tooltip for unsupported browsers)
- [ ] 2.5 Implement error state (brief error indicator + toast notification)
- [ ] 2.6 Add keyboard activation (Enter/Space toggle)

## 3. Chat Input Integration

- [ ] 3.1 Add `VoiceInputButton` to `ChatInput.tsx` adjacent to the send button
- [ ] 3.2 Wire `useVoiceInput` to append final transcript to textarea content
- [ ] 3.3 Display interim transcript in textarea with reduced opacity styling
- [ ] 3.4 Implement auto-submit behavior (when enabled, submit on final result in single-utterance mode)
- [ ] 3.5 Auto-resize textarea after voice transcript insertion

## 4. Search Input Integration

- [ ] 4.1 Add `VoiceInputButton` inside the main search input (right side)
- [ ] 4.2 Wire voice transcript to replace search text and trigger search automatically

## 5. Backend Voice Input Settings

- [ ] 5.1 Extend `voice_settings_routes.py` to include `input_language`, `input_continuous`, `input_auto_submit` fields
- [ ] 5.2 Add defaults: `input_language="en-US"`, `input_continuous="false"`, `input_auto_submit="false"`
- [ ] 5.3 Add `PUT /api/v1/settings/voice/input_language` with BCP-47 validation
- [ ] 5.4 Add `PUT /api/v1/settings/voice/input_continuous` with boolean validation
- [ ] 5.5 Add `PUT /api/v1/settings/voice/input_auto_submit` with boolean validation
- [ ] 5.6 Add `DELETE` endpoints for each voice input field (reset to default)

## 6. Frontend Voice Input Settings UI

- [ ] 6.1 Add Voice Input subsection to `VoiceConfigurator.tsx` below existing TTS settings
- [ ] 6.2 Add language selector dropdown (English US, English UK, Spanish, French, German, Japanese, Chinese)
- [ ] 6.3 Add continuous mode toggle with description
- [ ] 6.4 Add auto-submit toggle with description
- [ ] 6.5 Wire settings to `use-settings.ts` hooks (query + mutations for voice input fields)
- [ ] 6.6 Add source badges (env/db/default) for voice input settings

## 7. LLM Transcript Cleanup — Backend

- [ ] 7.1 Create `POST /api/v1/voice/cleanup` endpoint accepting `{ "text": "..." }` and returning `{ "cleaned_text": "..." }`
- [ ] 7.2 Add cleanup prompt template (fix grammar, remove filler words, structure text, preserve intent)
- [ ] 7.3 Add `VOICE_CLEANUP = "voice_cleanup"` to `ModelStep` enum in `src/config/models.py`
- [ ] 7.4 Add `voice_cleanup: claude-haiku-4-5` to `default_models` in `src/config/model_registry.yaml`
- [ ] 7.5 Add `voice_cleanup` parameter to `ModelConfig.__init__()` and wire to `self._models`
- [ ] 7.6 Wire cleanup endpoint to use `model_config.get_model_for_step(ModelStep.VOICE_CLEANUP)`
- [ ] 7.7 Update model settings test step count assertion in `tests/api/test_model_settings_api.py`

## 8. LLM Transcript Cleanup — Frontend

- [ ] 8.1 Create `CleanupButton` component (sparkle/wand icon) with loading spinner state
- [ ] 8.2 Add `CleanupButton` to `ChatInput.tsx` adjacent to `VoiceInputButton`
- [ ] 8.3 Add `POST /api/v1/voice/cleanup` API client function in `web/src/lib/api/`
- [ ] 8.4 Wire cleanup button to call API, replace textarea content with cleaned text
- [ ] 8.5 Implement voice key phrase detection ("clean up") in continuous mode to auto-trigger cleanup
- [ ] 8.6 Add keyboard shortcut `Ctrl+Shift+C` / `Cmd+Shift+C` for cleanup
- [ ] 8.7 Handle cleanup errors (preserve original text, show error toast)
- [ ] 8.8 Add cleanup key phrase configuration to voice input settings

## 9. Accessibility

- [ ] 9.1 Add ARIA live region for voice input state announcements ("Recording started", "Recording stopped")
- [ ] 9.2 Ensure focus returns to input field when voice input stops
- [ ] 9.3 Position cursor at end of inserted text after transcript insertion

## 10. Testing

- [ ] 10.1 Add E2E test for voice input button rendering in ChatInput
- [ ] 10.2 Add E2E test for voice input button rendering in search
- [ ] 10.3 Add E2E test for voice input settings UI (language, continuous, auto-submit toggles)
- [ ] 10.4 Add E2E test for disabled state on unsupported browsers (mock `SpeechRecognition` as undefined)
- [ ] 10.5 Add backend tests for voice input settings API endpoints (GET, PUT, DELETE)
- [ ] 10.6 Add backend tests for voice cleanup API endpoint
- [ ] 10.7 Add E2E test for cleanup button rendering and click flow (mocked API)
- [ ] 10.8 Add E2E test for cleanup keyboard shortcut
