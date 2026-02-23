## 1. Voice Input Hook

- [x] 1.1 Create `web/src/hooks/use-voice-input.ts` with `useVoiceInput` hook wrapping SpeechRecognition API
- [x] 1.2 Implement feature detection (`isSupported`) for `SpeechRecognition` / `webkitSpeechRecognition`
- [x] 1.3 Implement `startListening`, `stopListening`, `toggleListening` control methods
- [x] 1.4 Implement interim transcript (`interimTranscript`) and final transcript (`transcript`) state
- [x] 1.5 Implement `continuous` mode and `lang` configuration options
- [x] 1.6 Implement `resetTranscript` method
- [x] 1.7 Handle all SpeechRecognition error events (`not-allowed`, `no-speech`, `network`, `audio-capture`) with user-facing messages

## 2. Voice Input Button Component

- [x] 2.1 Create `web/src/components/voice/VoiceInputButton.tsx` with microphone icon (Lucide `Mic` / `MicOff`)
- [x] 2.2 Implement idle state (mic icon, `aria-label="Start voice input"`)
- [x] 2.3 Implement recording state (pulsing red ring animation, `aria-label="Stop voice input"`)
- [x] 2.4 Implement disabled state (`aria-disabled="true"`, tooltip for unsupported browsers)
- [x] 2.5 Implement error state (brief error indicator + toast notification)
- [x] 2.6 Add keyboard activation (Enter/Space toggle)

## 3. Chat Input Integration

- [x] 3.1 Add `VoiceInputButton` to `ChatInput.tsx` adjacent to the send button
- [x] 3.2 Wire `useVoiceInput` to append final transcript to textarea content
- [x] 3.3 Display interim transcript in textarea with reduced opacity styling
- [x] 3.4 Implement auto-submit behavior (when enabled, submit on final result in single-utterance mode)
- [x] 3.5 Auto-resize textarea after voice transcript insertion

## 4. Search Input Integration

- [x] 4.1 Add `VoiceInputButton` inside the main search input (right side)
- [x] 4.2 Wire voice transcript to replace search text and trigger search automatically

## 5. Backend Voice Input Settings

- [x] 5.1 Extend `voice_settings_routes.py` to include `input_language`, `input_continuous`, `input_auto_submit` fields
- [x] 5.2 Add defaults: `input_language="en-US"`, `input_continuous="false"`, `input_auto_submit="false"`
- [x] 5.3 Add `PUT /api/v1/settings/voice/input_language` with BCP-47 validation
- [x] 5.4 Add `PUT /api/v1/settings/voice/input_continuous` with boolean validation
- [x] 5.5 Add `PUT /api/v1/settings/voice/input_auto_submit` with boolean validation
- [x] 5.6 Add `DELETE` endpoints for each voice input field (reset to default)

## 6. Frontend Voice Input Settings UI

- [x] 6.1 Add Voice Input subsection to `VoiceConfigurator.tsx` below existing TTS settings
- [x] 6.2 Add language selector dropdown (English US, English UK, Spanish, French, German, Japanese, Chinese)
- [x] 6.3 Add continuous mode toggle with description
- [x] 6.4 Add auto-submit toggle with description
- [x] 6.5 Wire settings to `use-settings.ts` hooks (query + mutations for voice input fields)
- [x] 6.6 Add source badges (env/db/default) for voice input settings

## 7. LLM Transcript Cleanup — Backend

- [x] 7.1 Create `POST /api/v1/voice/cleanup` endpoint accepting `{ "text": "..." }` and returning `{ "cleaned_text": "..." }`
- [x] 7.2 Add cleanup prompt template (fix grammar, remove filler words, structure text, preserve intent)
- [x] 7.3 Add `VOICE_CLEANUP = "voice_cleanup"` to `ModelStep` enum in `src/config/models.py`
- [x] 7.4 Add `voice_cleanup: claude-haiku-4-5` to `default_models` in `src/config/model_registry.yaml`
- [x] 7.5 Add `voice_cleanup` parameter to `ModelConfig.__init__()` and wire to `self._models`
- [x] 7.6 Wire cleanup endpoint to use `model_config.get_model_for_step(ModelStep.VOICE_CLEANUP)`
- [x] 7.7 Update model settings test step count assertion in `tests/api/test_model_settings_api.py`

## 8. LLM Transcript Cleanup — Frontend

- [x] 8.1 Create `CleanupButton` component (sparkle/wand icon) with loading spinner state
- [x] 8.2 Add `CleanupButton` to `ChatInput.tsx` adjacent to `VoiceInputButton`
- [x] 8.3 Add `POST /api/v1/voice/cleanup` API client function in `web/src/lib/api/`
- [x] 8.4 Wire cleanup button to call API, replace textarea content with cleaned text
- [x] 8.5 Implement voice key phrase detection ("clean up") in continuous mode to auto-trigger cleanup
- [x] 8.6 Add keyboard shortcut `Ctrl+Shift+C` / `Cmd+Shift+C` for cleanup
- [x] 8.7 Handle cleanup errors (preserve original text, show error toast)
- [ ] 8.8 Add cleanup key phrase configuration to voice input settings (deferred — key phrase is hardcoded to "clean up" for now; will be configurable in a follow-up)

## 9. Accessibility

- [x] 9.1 Add ARIA live region for voice input state announcements ("Recording started", "Recording stopped")
- [x] 9.2 Ensure focus returns to input field when voice input stops
- [x] 9.3 Position cursor at end of inserted text after transcript insertion

## 10. Testing

- [ ] 10.1 Add E2E test for voice input button rendering in ChatInput (deferred — no chat E2E page object yet)
- [ ] 10.2 Add E2E test for voice input button rendering in search (deferred — SpeechRecognition not available in Playwright)
- [x] 10.3 Add E2E test for voice input settings UI (language, continuous, auto-submit toggles)
- [ ] 10.4 Add E2E test for disabled state on unsupported browsers (deferred — SpeechRecognition not available in Playwright)
- [x] 10.5 Add backend tests for voice input settings API endpoints (GET, PUT, DELETE)
- [x] 10.6 Add backend tests for voice cleanup API endpoint
- [ ] 10.7 Add E2E test for cleanup button rendering and click flow (deferred — no chat E2E page object yet)
- [ ] 10.8 Add E2E test for cleanup keyboard shortcut (deferred — no chat E2E page object yet)

## Migration Notes
Open tasks migrated to beads issues on 2026-02-23:
- 8.8 → aca-fyh (Add configurable voice cleanup key phrase, P3)
- 10.1, 10.7, 10.8 → aca-gd0 (Add chat voice input E2E tests, P3)
- 10.2, 10.4 → aca-qp8 (Add SpeechRecognition E2E tests with browser mock, P4)
