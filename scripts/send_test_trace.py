#!/usr/bin/env python3
"""Send a test trace to an OTLP endpoint.

Usage:
    python scripts/send_test_trace.py [--endpoint URL] [--service NAME]

Examples:
    # Send to local Opik (default)
    python scripts/send_test_trace.py

    # Send to custom endpoint
    python scripts/send_test_trace.py --endpoint http://localhost:4318/v1/traces

    # With custom service name
    python scripts/send_test_trace.py --service my-test-service

    # With Basic Auth (for Langfuse)
    python scripts/send_test_trace.py --endpoint http://localhost:3100/api/public/otel/v1/traces \\
        --basic-auth pk-lf-xxx:sk-lf-yyy
"""

import argparse
import base64
import sys

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Default to local Opik OTLP endpoint
DEFAULT_ENDPOINT = "http://localhost:5174/api/v1/private/otel/v1/traces"
DEFAULT_SERVICE = "test-trace-sender"


def send_test_trace(endpoint: str, service_name: str, basic_auth: str | None = None) -> bool:
    """Send a test trace to the specified OTLP endpoint.

    Returns True if successful, False otherwise.
    """
    try:
        # Create provider with service name
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Build headers (e.g., Basic Auth for Langfuse)
        headers: dict[str, str] = {}
        if basic_auth:
            encoded = base64.b64encode(basic_auth.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        # Configure OTLP HTTP exporter
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set as global provider
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer(__name__)

        # Create test span
        with tracer.start_as_current_span("test-trace") as span:
            span.set_attribute("test.source", "send_test_trace.py")
            span.set_attribute("test.endpoint", endpoint)

        # Force flush to ensure span is exported
        provider.force_flush()

        return True

    except Exception as e:
        print(f"Error sending trace: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test trace to an OTLP endpoint")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"OTLP HTTP endpoint (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--service",
        default=DEFAULT_SERVICE,
        help=f"Service name for the trace (default: {DEFAULT_SERVICE})",
    )
    parser.add_argument(
        "--basic-auth",
        help="Basic auth credentials (user:password) for OTLP endpoint",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output on success",
    )

    args = parser.parse_args()

    success = send_test_trace(args.endpoint, args.service, args.basic_auth)

    if success:
        if not args.quiet:
            print(f"✓ Test trace sent to {args.endpoint}")
        return 0
    else:
        print(f"✗ Failed to send trace to {args.endpoint}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
