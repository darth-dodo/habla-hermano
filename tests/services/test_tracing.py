"""Tests for src/services/tracing.py: optional Langfuse tracing, metadata only in production."""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langfuse.types import MaskOtelSpansParams

from src.services import tracing


def _params(attributes: dict[str, object]) -> MaskOtelSpansParams:
    span = SimpleNamespace(attributes=attributes)
    return MaskOtelSpansParams(spans={"span-1": span})  # type: ignore[arg-type,dict-item]


class TestMaskContent:
    """Production traces must not carry learner or Hermano text, or user IDs."""

    def test_drops_input_output_and_private_metadata(self) -> None:
        result = tracing.mask_content(
            params=_params(
                {
                    "langfuse.observation.input": '{"messages": "Ayer yo voy a la playa"}',
                    "langfuse.observation.output": "Ayer fui a la playa",
                    "langfuse.observation.metadata.thread_id": '"user:1234"',
                    "langfuse.trace.metadata.langfuse_session_id_raw": '"x"',
                    "langfuse.observation.metadata.langgraph_node": '"analyze"',
                    "langfuse.observation.metadata.level": '"A2"',
                    "langfuse.observation.model.name": "anthropic/claude-haiku-5.5",
                    "langfuse.observation.usage_details": '{"input": 10}',
                }
            )
        )

        assert result is not None
        dropped = set(result.span_patches["span-1"].delete_attributes)
        assert dropped == {
            "langfuse.observation.input",
            "langfuse.observation.output",
            "langfuse.observation.metadata.thread_id",
            "langfuse.trace.metadata.langfuse_session_id_raw",
        }

    def test_span_without_private_attributes_is_left_alone(self) -> None:
        params = _params({"langfuse.observation.model.name": "m", "session.id": "abc"})
        assert tracing.mask_content(params=params) is None


@pytest.fixture
def reset_handler() -> Iterator[None]:
    tracing._handler = None
    yield
    tracing._handler = None


def _settings(**overrides: object) -> SimpleNamespace:
    values = {
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",  # pragma: allowlist secret
        "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        "DEBUG": False,
        "SECRET_KEY": "test-secret",  # pragma: allowlist secret
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.usefixtures("reset_handler")
class TestTracingConfig:
    """tracing_config() adds the callback only when keys are set."""

    def test_off_without_keys(self) -> None:
        with patch.object(tracing, "get_settings", return_value=_settings(LANGFUSE_SECRET_KEY="")):
            assert tracing.tracing_config("user:abc", level="A1", language="es") == {}

    @pytest.mark.parametrize(("debug", "masked"), [(False, True), (True, False)])
    def test_on_with_keys(self, debug: bool, masked: bool) -> None:
        client_cls, handler_cls = MagicMock(), MagicMock()
        with (
            patch.object(tracing, "get_settings", return_value=_settings(DEBUG=debug)),
            patch("langfuse.Langfuse", client_cls),
            patch("langfuse.langchain.CallbackHandler", handler_cls),
        ):
            config = tracing.tracing_config("user:abc-123", level="A1", language="es")
            again = tracing.tracing_config("user:abc-123", level="A1", language="es")

        assert config["callbacks"] == [handler_cls.return_value]
        assert client_cls.call_count == 1  # one client per process
        mask = client_cls.call_args.kwargs["mask_otel_spans"]
        assert (mask is tracing.mask_content) is masked
        metadata = config["metadata"]
        assert metadata["level"] == "A1" and metadata["language"] == "es"
        # Same conversation, same session; the raw thread ID never leaves the server.
        assert metadata["langfuse_session_id"] == again["metadata"]["langfuse_session_id"]
        assert "abc-123" not in metadata["langfuse_session_id"]
