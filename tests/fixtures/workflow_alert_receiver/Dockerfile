FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY tests/fixtures/workflow_alert_receiver/app.py ./receiver_app.py

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["uvicorn", "receiver_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
