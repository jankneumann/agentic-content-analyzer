# Change: Add AI Image Generator Service

## Why

The unified content model includes an `Image` entity with support for `AI_GENERATED` source type, but there's no service to actually generate images. AI-generated images would enhance:

1. **Summary Visualization**: Generate diagrams, charts, or illustrations that help explain complex technical concepts in newsletter summaries
2. **Digest Enhancement**: Create cohesive visual themes across daily/weekly digests
3. **Social Media Sharing**: Generate engaging images for content promotion
4. **Accessibility**: Provide visual alternatives to text-heavy content

The Image model already has fields for:
- `generation_prompt` - The prompt used to generate the image
- `generation_model` - The AI model used (DALL-E, Midjourney, etc.)
- `generation_params` - Additional parameters (style, size, etc.)

## What Changes

- **Create `src/services/image_generator.py`** with:
  - `ImageGenerator` class for AI image generation
  - `generate_for_summary()` - Generate images for newsletter summaries
  - `generate_for_digest()` - Generate images for digests
  - `suggest_images()` - Analyze content and suggest image generation opportunities
  - Provider abstraction for multiple AI services (OpenAI DALL-E, Stability AI, etc.)

- **Add configuration** for:
  - Default image generation model
  - API keys for image providers
  - Generation parameters (style, quality, size)

- **Integrate with revision workflow**:
  - Allow reviewers to request image generation during summary/digest review
  - Store generation metadata for reproducibility

## Impact

- **Affected specs**: New capability (image-generation)
- **Affected code**:
  - `src/services/image_generator.py` - New service
  - `src/config/settings.py` - New configuration options
  - `src/api/image_routes.py` - API endpoints for generation
  - `src/services/review_service.py` - Integration with review workflow
- **Dependencies**:
  - OpenAI Python SDK (for DALL-E)
  - Optional: Stability AI SDK
- **Breaking changes**: None (additive feature)

## Status

**Not Started** - Proposal created, awaiting approval.

## Related Proposals

### Dependencies

- **Depends on**: `refactor-unified-content-model` (Image model and storage)
- **Related**: `content-sharing` (may use generated images)

### Prior Art

The Image model and storage infrastructure were implemented as part of `refactor-unified-content-model`. This proposal focuses solely on the AI generation capability.
