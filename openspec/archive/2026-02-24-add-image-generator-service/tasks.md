# Tasks: Add AI Image Generator Service

## 1. Core Service Implementation

- [x] 1.1 Create `src/services/image_generator.py`:
  - Abstract `ImageGeneratorProvider` base class
  - `GeminiImageGenerator` implementation (Imagen via Vertex AI)
  - Factory function `get_image_generator()`
- [x] 1.2 Implement `generate_for_summary(summary, prompt) -> Image`:
  - Accept summary context and generation prompt
  - Call AI provider API
  - Upload result to image storage (S3/local)
  - Create Image record with `AI_GENERATED` source type
  - Store `generation_prompt`, `generation_model`, `generation_params`
- [x] 1.3 Implement `generate_for_digest(digest, prompt) -> Image`:
  - Similar to summary generation
  - Support digest-specific styling
- [x] 1.4 Implement `suggest_images(content: str) -> list[ImageSuggestion]`:
  - Analyze content for visualization opportunities
  - Identify concepts that benefit from visual explanation
  - Return structured suggestions with prompts and rationale

## 2. Configuration

- [x] 2.1 Add settings to `src/config/settings.py`:
  - `IMAGE_GENERATION_ENABLED: bool` - Feature flag
  - `IMAGE_GENERATION_PROVIDER: str` - "gemini", "openai", "stability"
  - `IMAGE_GENERATION_MODEL: str` - Model ID (e.g., "imagen-3.0-generate-001")
  - `IMAGE_GENERATION_DEFAULT_SIZE: str` - Default dimensions
  - `IMAGE_GENERATION_DEFAULT_QUALITY: str` - "standard" or "hd"
  - `IMAGE_GENERATION_DEFAULT_STYLE: str` - Generation style
- [x] 2.2 Add credentials to environment:
  - `GOOGLE_CLOUD_PROJECT` - GCP project ID for Vertex AI
  - `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON
  - `OPENAI_API_KEY` (optional, for future DALL-E support)

## 3. Pydantic Schemas

- [x] 3.1 Create `ImageSuggestion` schema:
  - `prompt: str` - Suggested generation prompt
  - `rationale: str` - Why this image would help
  - `style: str` - Suggested style
  - `placement: str` - Where in content to place
- [x] 3.2 Create `ImageGenerationRequest` schema:
  - `prompt: str` - Generation prompt
  - `style: str | None` - Style override
  - `size: str | None` - Size override
  - `quality: str | None` - Quality override
- [x] 3.3 Create `ImageGenerationResponse` schema:
  - `image_id: UUID` - Created image ID
  - `url: str` - Storage URL
  - `prompt: str` - Used prompt
  - `model: str` - Used model

## 4. API Endpoints

- [x] 4.1 Create `src/api/image_generation_routes.py`:
  - `POST /api/v1/images/generate` - Generate new image
  - `POST /api/v1/images/suggest` - Get suggestions for content
  - `POST /api/v1/images/{id}/regenerate` - Regenerate with same prompt
- [ ] 4.2 Add rate limiting for generation endpoints
- [x] 4.3 Register routes in `src/api/app.py`

## 5. Review Workflow Integration

- [ ] 5.1 Update `src/services/review_service.py`:
  - Add `request_image_generation()` method
  - Store generation requests in revision history
- [ ] 5.2 Update Summary/Digest review UI (future):
  - Add "Generate Image" button
  - Show suggestions panel
  - Preview generated images before insertion

## 6. Testing

- [x] 6.1 Unit tests for ImageGenerator:
  - Mock AI provider responses
  - Test image storage integration
  - Test metadata storage
- [x] 6.2 Unit tests for suggestion generation:
  - Test content analysis
  - Test prompt generation
- [x] 6.3 API endpoint tests:
  - Test generation flow
  - Test rate limiting
  - Test error handling

## 7. Documentation

- [x] 7.1 Document configuration options in SETUP.md
- [x] 7.2 Document API endpoints in ARCHITECTURE.md
- [x] 7.3 Create usage guide for image generation feature

## Notes

- Task 4.2 (rate limiting) deferred — requires design decision on limits and token bucket vs sliding window approach
- Task 5.1-5.2 (review workflow integration) deferred — depends on broader review UI refactoring
- Prompt configurability is fully implemented via `prompts.yaml` and PromptService (pipeline.image_generation.*)

## Migration Notes

Open tasks migrated to beads issues on 2026-02-24:
- Task 4.2 (rate limiting) → aca-m6m
- Task 5.1 (review service integration) → aca-v27
- Task 5.2 (review UI) → aca-4ht (blocked by aca-v27)
