"""Tests for TracingMiddleware and Tracer/Span."""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestTracingMiddleware:
    @pytest.mark.asyncio
    async def test_no_tracer_no_metrics(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        mw = TracingMiddleware()
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_with_metrics_success(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        metrics = MagicMock()
        counter = MagicMock()
        counter.inc = MagicMock()
        metrics.counter.return_value = counter
        hist = MagicMock()
        metrics.histogram.return_value = hist

        mw = TracingMiddleware(metrics=metrics)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "ok"
        metrics.counter.assert_called()
        hist.observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_metrics_error_result(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        metrics = MagicMock()
        counter = MagicMock()
        counter.inc = MagicMock()
        metrics.counter.return_value = counter
        hist = MagicMock()
        metrics.histogram.return_value = hist

        mw = TracingMiddleware(metrics=metrics)
        next_call = AsyncMock(return_value={"status": "error", "msg": "fail"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_with_tracer_success(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        tracer = MagicMock()
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        tracer.span.return_value = span

        mw = TracingMiddleware(tracer=tracer)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_with_tracer_error_result(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        tracer = MagicMock()
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        tracer.span.return_value = span

        mw = TracingMiddleware(tracer=tracer)
        next_call = AsyncMock(return_value={"status": "error", "msg": "fail"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "error"
        span.set_status.assert_called_once_with("error")

    @pytest.mark.asyncio
    async def test_with_tracer_and_metrics(self):
        from xcore.kernel.middlewares.tracing import TracingMiddleware
        tracer = MagicMock()
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        tracer.span.return_value = span

        metrics = MagicMock()
        counter = MagicMock()
        counter.inc = MagicMock()
        metrics.counter.return_value = counter
        hist = MagicMock()
        metrics.histogram.return_value = hist

        mw = TracingMiddleware(tracer=tracer, metrics=metrics)
        next_call = AsyncMock(return_value={"status": "error"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "error"


class TestTracer:
    def test_span_success(self):
        from xcore.kernel.observability.tracing import Tracer
        t = Tracer("test")
        with t.span("op") as span:
            span.set_attribute("k", "v")
        assert len(t._spans) == 1
        assert t._spans[0].attributes["k"] == "v"
        assert t._spans[0].duration_ms is not None

    def test_span_error(self):
        from xcore.kernel.observability.tracing import Tracer
        t = Tracer("test")
        with pytest.raises(ValueError):
            with t.span("op") as span:
                raise ValueError("boom")
        assert t._spans[0].status == "error"

    def test_export(self):
        from xcore.kernel.observability.tracing import Tracer
        t = Tracer("test")
        with t.span("my_op") as span:
            pass
        exported = t.export()
        assert len(exported) == 1
        assert exported[0]["name"] == "my_op"
        assert "duration_ms" in exported[0]
        assert "trace_id" in exported[0]

    def test_noop_tracer(self):
        from xcore.kernel.observability.tracing import noop_tracer
        t = noop_tracer()
        assert t.service_name == "noop"

    def test_span_duration_none_before_end(self):
        from xcore.kernel.observability.tracing import Span
        s = Span(name="test")
        assert s.duration_ms is None
        s.end()
        assert s.duration_ms is not None


class TestXcoreLogger:
    def test_logging_all_levels(self):
        from xcore.kernel.observability.logging import get_logger
        import logging
        logger = get_logger("test.unit")
        logger._log.setLevel(logging.DEBUG)
        # Should not raise
        logger.debug("debug msg", key="val")
        logger.info("info msg", key="val")
        logger.warning("warn msg")
        logger.error("error msg", err="oops")
        logger.critical("crit msg")

    def test_logger_name(self):
        from xcore.kernel.observability.logging import get_logger
        logger = get_logger("mymodule")
        assert "xcore" in logger.name

    def test_logger_is_enabled_for(self):
        from xcore.kernel.observability.logging import get_logger
        import logging
        logger = get_logger("test.enabled")
        result = logger.isEnabledFor(logging.WARNING)
        assert isinstance(result, bool)

    def test_configure_logging_json(self):
        from xcore.kernel.observability.logging import configure_logging
        cfg = MagicMock()
        cfg.level = "DEBUG"
        cfg.output = "json"
        cfg.file = None
        import logging
        root = logging.getLogger("xcore")
        root.handlers.clear()
        configure_logging(cfg)
        assert len(root.handlers) >= 1

    def test_configure_logging_text(self):
        from xcore.kernel.observability.logging import configure_logging
        cfg = MagicMock()
        cfg.level = "INFO"
        cfg.output = "text"
        cfg.file = None
        import logging
        root = logging.getLogger("xcore")
        root.handlers.clear()
        configure_logging(cfg)
        assert len(root.handlers) >= 1

    def test_configure_logging_with_file(self, tmp_path):
        from xcore.kernel.observability.logging import configure_logging
        cfg = MagicMock()
        cfg.level = "INFO"
        cfg.output = "text"
        cfg.file = str(tmp_path / "app.log")
        cfg.max_bytes = 1024 * 1024
        cfg.backup_count = 3
        import logging
        root = logging.getLogger("xcore")
        root.handlers.clear()
        configure_logging(cfg)
        # cleanup
        for h in root.handlers[:]:
            if hasattr(h, 'baseFilename'):
                h.close()
                root.removeHandler(h)

    def test_exception_method(self):
        from xcore.kernel.observability.logging import get_logger
        import logging
        logger = get_logger("test.exc")
        logger._log.setLevel(logging.DEBUG)
        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("caught an error", ctx="test")  # should not raise

    def test_text_formatter_with_exc_info(self):
        from xcore.kernel.observability.logging import _TextFormatter
        import logging
        formatter = _TextFormatter()
        record = logging.LogRecord("test", logging.ERROR, "", 0, "msg", (), None)
        try:
            raise ValueError("oops")
        except ValueError:
            import sys
            record.exc_info = sys.exc_info()
        result = formatter.format(record)
        assert "oops" in result

    def test_json_formatter_with_exc_info(self):
        from xcore.kernel.observability.logging import _JsonFormatter
        import json, logging
        formatter = _JsonFormatter()
        record = logging.LogRecord("test", logging.ERROR, "", 0, "msg", (), None)
        try:
            raise ValueError("json_oops")
        except ValueError:
            import sys
            record.exc_info = sys.exc_info()
        result = formatter.format(record)
        data = json.loads(result)
        assert "trace" in data
