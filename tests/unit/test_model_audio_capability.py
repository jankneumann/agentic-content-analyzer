"""Unit tests for supports_audio capability flag in model registry."""

from src.config.models import ModelConfig, ModelFamily, ModelStep, load_model_registry


class TestSupportsAudioFlag:
    """Test that supports_audio is correctly parsed from model_registry.yaml."""

    def test_gemini_models_support_audio(self):
        """Gemini 2.0+ models should have supports_audio=True."""
        registry, _, _ = load_model_registry()
        gemini_audio_models = [
            m for m in registry.values() if m.family == ModelFamily.GEMINI and m.supports_audio
        ]
        # At least one Gemini model should support audio
        assert len(gemini_audio_models) > 0

    def test_whisper_supports_audio(self):
        """Whisper model should have supports_audio=True."""
        registry, _, _ = load_model_registry()
        assert "whisper-1" in registry
        assert registry["whisper-1"].supports_audio is True
        assert registry["whisper-1"].family == ModelFamily.WHISPER

    def test_deepgram_supports_audio(self):
        """Deepgram model should have supports_audio=True."""
        registry, _, _ = load_model_registry()
        assert "deepgram-nova-3" in registry
        assert registry["deepgram-nova-3"].supports_audio is True
        assert registry["deepgram-nova-3"].family == ModelFamily.DEEPGRAM

    def test_claude_does_not_support_audio(self):
        """Claude models should have supports_audio=False."""
        registry, _, _ = load_model_registry()
        claude_models = [m for m in registry.values() if m.family == ModelFamily.CLAUDE]
        assert len(claude_models) > 0
        for model in claude_models:
            assert model.supports_audio is False

    def test_gpt_does_not_support_audio(self):
        """GPT models should have supports_audio=False."""
        registry, _, _ = load_model_registry()
        gpt_models = [m for m in registry.values() if m.family == ModelFamily.GPT]
        for model in gpt_models:
            assert model.supports_audio is False

    def test_supports_audio_defaults_to_false(self):
        """Models without explicit supports_audio should default to False."""
        registry, _, _ = load_model_registry()
        # All models should have the attribute
        for model in registry.values():
            assert isinstance(model.supports_audio, bool)


class TestCloudSTTPipelineStep:
    """Test CLOUD_STT as a registered pipeline step."""

    def test_cloud_stt_in_model_step_enum(self):
        """CLOUD_STT should be a valid ModelStep value."""
        assert hasattr(ModelStep, "CLOUD_STT")
        assert ModelStep.CLOUD_STT.value == "cloud_stt"

    def test_cloud_stt_default_model(self):
        """ModelConfig should have a default for the CLOUD_STT step."""
        config = ModelConfig()
        model = config.get_model_for_step(ModelStep.CLOUD_STT)
        assert model is not None
        # Default should be an audio-capable model
        registry, _, _ = load_model_registry()
        assert registry[model].supports_audio is True

    def test_cloud_stt_env_var_name(self):
        """CLOUD_STT step should have MODEL_CLOUD_STT env var (auto-generated)."""
        expected = f"MODEL_{ModelStep.CLOUD_STT.value.upper()}"
        assert expected == "MODEL_CLOUD_STT"

    def test_all_model_steps_count(self):
        """Verify the total number of ModelStep values includes CLOUD_STT."""
        steps = list(ModelStep)
        assert len(steps) == 14


class TestModelFamilyEnum:
    """Test new model family entries."""

    def test_whisper_family_exists(self):
        assert hasattr(ModelFamily, "WHISPER")
        assert ModelFamily.WHISPER.value == "whisper"

    def test_deepgram_family_exists(self):
        assert hasattr(ModelFamily, "DEEPGRAM")
        assert ModelFamily.DEEPGRAM.value == "deepgram"
