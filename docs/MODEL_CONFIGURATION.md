# Model Selection & Configuration

The system uses a flexible, YAML-based model configuration system that supports multiple LLM providers with automatic failover and per-provider pricing.

## Architecture Overview

The model configuration system consists of three layers:

1. **Model Registry** (`src/config/model_registry.yaml`): Defines all available models, their providers, and pricing
2. **ModelConfig Class** (`src/config/models.py`): Python interface for model selection and provider management
3. **Processor Integration**: Each processor (summarizer, theme analyzer, digest creator) uses ModelConfig

## Pipeline Steps

The newsletter processing pipeline has four distinct LLM steps, each configurable independently:

| Step | Purpose | Default Model | Optimization Strategy |
|------|---------|---------------|----------------------|
| **SUMMARIZATION** | Extract key points from individual newsletters | Claude Haiku | Fast, cost-effective for straightforward extraction |
| **THEME_ANALYSIS** | Identify patterns across multiple summaries | Claude Sonnet | Quality-critical; benefits from stronger reasoning |
| **DIGEST_CREATION** | Generate multi-audience formatted output | Claude Sonnet | Quality-critical; customer-facing content |
| **HISTORICAL_CONTEXT** | Query knowledge graph for related themes | Claude Haiku | Simple queries; speed matters |

## Model ID System

The project uses **family-based model IDs** for user-facing configuration, while internally managing provider-specific identifiers for API calls.

### Family-Based IDs

**What you use in code and config:**

- Format: `claude-sonnet-4-5` (no version dates)
- Stable across provider and version updates
- Used in: Environment variables, ModelConfig, database `model_used` field
- Example: `config = ModelConfig(summarization="claude-haiku-4-5")`

### Provider-Specific IDs

**Managed internally:**

- Format varies by provider:
  - Anthropic: `claude-sonnet-4-5-20250929` (includes release date)
  - AWS Bedrock: `anthropic.claude-sonnet-4-5-20250929-v1:0` (namespace prefix)
  - Google Vertex AI: `claude-sonnet-4-5@20250929` (@ separator)
- Stored in `model_registry.yaml` under `provider_model_id`
- Automatically selected for API calls based on provider
- Version tracked separately in database `model_version` field

### Benefits

- **Multi-version support**: Different providers can use different release versions
- **Cleaner code**: No version dates in application code
- **Easier updates**: Change provider-specific IDs without code changes
- **Better tracking**: Separate general ID and version in database

### Example

```python
# You use family-based ID
config = ModelConfig(summarization="claude-sonnet-4-5")

# System automatically uses correct provider ID for API:
# - Anthropic: "claude-sonnet-4-5-20250929"
# - AWS Bedrock: "anthropic.claude-sonnet-4-5-20250929-v1:0"
# - Vertex AI: "claude-sonnet-4-5@20250929"
```

## Configuration Methods

### 1. Environment-Based (Recommended for Production)

Set model IDs via environment variables (defined in `.env`):

```bash
# Use Haiku for cost optimization (family-based IDs)
MODEL_SUMMARIZATION=claude-haiku-4-5
MODEL_THEME_ANALYSIS=claude-haiku-4-5
MODEL_DIGEST_CREATION=claude-haiku-4-5
MODEL_HISTORICAL_CONTEXT=claude-haiku-4-5

# Provider API keys
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Code-Based Configuration

For custom workflows or testing:

```python
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig

# Configure specific models per step (using family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",      # Fast extraction
    theme_analysis="claude-sonnet-4-5",    # Better reasoning
    digest_creation="claude-sonnet-4-5",   # Quality output
    historical_context="claude-haiku-4-5", # Simple queries
    providers=[
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="sk-ant-...")
    ]
)

# Use in processors
from src.processors.summarizer import NewsletterSummarizer
summarizer = NewsletterSummarizer(model_config=config)
```

### 3. Model Override at Runtime

Override model for specific operations:

```python
# Override model for a single operation
from src.agents.claude import ClaudeAgent

agent = ClaudeAgent(
    model_config=config,
    model="claude-opus-4-5"  # Override to highest quality (family-based ID)
)
```

## Provider Configuration & Failover

### Multi-Provider Setup

Configure multiple providers for the same model (automatic failover):

```python
config = ModelConfig(
    providers=[
        # Primary: Direct Anthropic API
        ProviderConfig(
            provider=Provider.ANTHROPIC,
            api_key="sk-ant-primary-...",
        ),
        # Backup: AWS Bedrock (different pricing)
        ProviderConfig(
            provider=Provider.AWS_BEDROCK,
            api_key="bedrock-key-...",
            region="us-east-1"
        ),
        # Tertiary: Vertex AI
        ProviderConfig(
            provider=Provider.VERTEX_AI,
            api_key="vertex-key-...",
            project_id="my-project"
        )
    ]
)
```

### Failover Behavior

- Providers are tried in order of configuration
- If primary fails (API error, rate limit), automatically tries next provider
- All failures are logged; last error is raised if all providers fail
- Provider used is tracked in `provider_used` attribute for cost calculation

### Provider-Specific Pricing

The same model costs differently on different providers:

```yaml
# In model_registry.yaml (family-based keys, provider-specific IDs)
anthropic.claude-sonnet-4-5:
  provider_model_id: "claude-sonnet-4-5-20250929"  # Provider-specific ID for API calls
  cost_per_mtok_input: 3.00   # $3/MTok
  cost_per_mtok_output: 15.00  # $15/MTok

aws_bedrock.claude-sonnet-4-5:
  provider_model_id: "anthropic.claude-sonnet-4-5-20250929-v1:0"  # Bedrock format
  cost_per_mtok_input: 3.00
  cost_per_mtok_output: 15.00

google_vertex.claude-sonnet-4-5:
  provider_model_id: "claude-sonnet-4-5@20250929"  # Vertex format
  cost_per_mtok_input: 3.00
  cost_per_mtok_output: 15.00
```

## Cost Optimization Strategies

### Strategy 1: Mixed Model Configuration (Recommended)

Use cheaper models for simple tasks, premium models for quality-critical steps:

```python
# Cost-optimized configuration (family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",      # $0.80/MTok input, $4/MTok output
    theme_analysis="claude-sonnet-4-5",    # $3/MTok input, $15/MTok output
    digest_creation="claude-sonnet-4-5",   # $3/MTok input, $15/MTok output
    historical_context="claude-haiku-4-5", # $0.80/MTok input, $4/MTok output
)

# Cost savings example (processing 100 newsletters):
# - Summarization: 100 newsletters × ~2K tokens = ~$0.80 (Haiku) vs ~$3.00 (Sonnet)
# - Theme analysis: 5 analyses × ~5K tokens = ~$0.38 (Sonnet)
# - Digest creation: 7 digests × ~8K tokens = ~$1.20 (Sonnet)
# Total: ~$2.38 vs ~$4.58 (all Sonnet) = 48% cost reduction
```

### Strategy 2: Quality-First Configuration

Use premium models for all steps when quality is paramount:

```python
# Maximum quality configuration (family-based IDs)
config = ModelConfig(
    summarization="claude-sonnet-4-5",
    theme_analysis="claude-opus-4-5",      # Highest reasoning capability
    digest_creation="claude-opus-4-5",
    historical_context="claude-sonnet-4-5",
)
```

### Strategy 3: Budget-Constrained Configuration

Use fastest, cheapest models for all steps:

```python
# Maximum cost savings (family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",
    theme_analysis="claude-haiku-4-5",
    digest_creation="claude-haiku-4-5",
    historical_context="claude-haiku-4-5",
)
```

### Cost Tracking

All processors track token usage and calculate costs:

```python
from src.processors.theme_analyzer import ThemeAnalyzer

analyzer = ThemeAnalyzer(model_config=config)
result = await analyzer.analyze_themes(request)

# Access cost data
print(f"Tokens: {result.token_usage} ({result.input_tokens} in, {result.output_tokens} out)")
print(f"Cost: ${result.cost:.4f}")
print(f"Model used: {result.model_used}")
print(f"Provider: {analyzer.provider_used.value}")
```

## Adding New Models

### 1. Add Model to Registry

Edit `src/config/model_registry.yaml`:

```yaml
models:
  # Add new model definition (family-based ID)
  claude-opus-4-5:
    family: claude
    name: "Claude 4.5 Opus"
    supports_vision: true
    supports_video: false
    default_version: "20251024"

provider_model_configs:
  # Add provider-specific configuration
  anthropic.claude-opus-4-5:
    provider_model_id: "claude-opus-4-5-20251024"  # Actual API identifier
    cost_per_mtok_input: 15.00
    cost_per_mtok_output: 75.00
    context_window: 200000
    max_output_tokens: 8192
```

### 2. Use New Model

Set in environment or code:

```bash
# Environment (use family-based ID)
MODEL_THEME_ANALYSIS=claude-opus-4-5
```

```python
# Code (use family-based ID)
config = ModelConfig(
    theme_analysis="claude-opus-4-5"
)
```

## Adding New Providers

### 1. Add Provider Enum

Edit `src/config/models.py`:

```python
class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    AWS_BEDROCK = "aws_bedrock"
    VERTEX_AI = "vertex_ai"
    AZURE_OPENAI = "azure_openai"
    MY_NEW_PROVIDER = "my_new_provider"  # Add here
```

### 2. Add Provider Configuration to YAML

```yaml
provider_model_configs:
  my_new_provider.claude-sonnet-4-5:
    provider_model_id: "provider-specific-identifier"  # Your provider's API identifier
    cost_per_mtok_input: 3.00
    cost_per_mtok_output: 15.00
    context_window: 200000
    max_output_tokens: 8192
```

### 3. Implement Provider Client (if needed)

For providers with different APIs, add implementation in processors:

```python
# In src/processors/theme_analyzer.py
def _call_llm_with_provider(self, provider_config: ProviderConfig, prompt: str):
    if provider_config.provider == Provider.MY_NEW_PROVIDER:
        # Custom implementation for new provider
        client = MyNewProviderClient(api_key=provider_config.api_key)
        response = client.generate(prompt=prompt, model=self.model)
        return response
    elif provider_config.provider == Provider.ANTHROPIC:
        # Existing implementation
        ...
```

## Testing Different Model Combinations

The test suite includes comprehensive tests for different model configurations:

```bash
# Run model combination tests
pytest tests/integration/test_e2e_model_combinations.py -v

# Tests include:
# - Haiku-only configuration (fast/cheap)
# - Sonnet-only configuration (quality)
# - Mixed configuration (optimized)
# - Cost calculation verification
# - Provider failover
# - Model override at agent level
```

## Configuration Best Practices

1. **Start with Mixed Configuration**: Use Haiku for summarization/historical context, Sonnet for theme analysis/digest creation
2. **Monitor Costs**: Track token usage and costs per pipeline run to optimize
3. **Test Before Production**: Use test configurations to verify behavior before changing production settings
4. **Provider Redundancy**: Configure at least 2 providers for production to handle API issues
5. **Environment Variables**: Use env vars for production; code-based config for testing
6. **Model Families**: Stick to same family (Claude) for consistency unless comparing frameworks

## Model Registry Reference

Current available models (see `model_registry.yaml` for full list):

**Note**: Model IDs are now family-based (no version dates). The system automatically uses the correct provider-specific identifier for API calls.

### Claude Family

- `claude-haiku-4-5`: Fastest, cheapest ($0.80/$4 per MTok)
- `claude-sonnet-4-5`: Balanced quality/cost ($3/$15 per MTok)
- `claude-opus-4-5`: Highest quality ($15/$75 per MTok)
- `claude-sonnet-4`: Legacy Claude Sonnet 4 ($3/$15 per MTok)

### Gemini Family

For framework comparison:

- `gemini-2.0-flash`: Fast, affordable, 1M context
- `gemini-2.0-pro`: High quality, 2M context

### OpenAI Family

- `gpt-4o`: Standard GPT-4o
- `gpt-4o-mini`: Smaller, faster GPT-4o
- `o1-mini`: Reasoning-focused model
- `gemini-2.0-pro-001`: Premium quality

### GPT Family

For framework comparison:

- `gpt-4.5-turbo-2025-02-27`: Latest GPT-4.5
- `gpt-4o-2024-11-20`: Multimodal GPT-4o

## Troubleshooting

### Model not found

Ensure model ID matches exactly in `model_registry.yaml`:

```python
# Check available models
from src.config.models import MODEL_REGISTRY
print(MODEL_REGISTRY.keys())
```

### Provider API error

Check API keys in `.env` and provider status:

```bash
# Verify environment variables
echo $ANTHROPIC_API_KEY
```

### Unexpected costs

Verify provider-specific pricing in YAML matches actual provider pricing:

```python
# Check cost calculation (use family-based ID)
cost = config.calculate_cost(
    model_id="claude-sonnet-4-5",
    input_tokens=1000,
    output_tokens=500,
    provider=Provider.ANTHROPIC
)
print(f"Estimated cost: ${cost:.4f}")
```
