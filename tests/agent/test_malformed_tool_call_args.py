"""A provider-confirmed stop with unparseable tool arguments is not an output cap.

Regression for the deepseek-v4.1-flash / Cloudflare shape: the model ended its own reply
mid tool-call JSON while reporting ``finish_reason="stop"``. The stream assembler still
stamps ``length`` (that stamp is what keeps the broken call from executing), but it tags the
response so the truncation handler words the failure correctly and does not burn four retries
doubling a ``max_tokens`` cap that was never sent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent
from agent.turn_failure_copy import site_copy
from agent.turn_truncation import _MALFORMED_TOOL_CALL_RETRIES, _Trunc, _retry_malformed_tool_call

_BROKEN_ARGS = '{"path": "a.py", "content": "print(1'


# ── stream assembly ──────────────────────────────────────────────────────────

def _make_stream_chunk(content=None, tool_calls=None, finish_reason=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=None, reasoning=None)
    return SimpleNamespace(choices=[SimpleNamespace(index=0, delta=delta, finish_reason=finish_reason)],
                           model=None, usage=None)


def _make_tool_call_delta(index=0, tc_id=None, name=None, arguments=None):
    return SimpleNamespace(index=index, id=tc_id, function=SimpleNamespace(name=name, arguments=arguments))


def _make_agent():
    agent = AIAgent(api_key="test-key", base_url="https://example.com/v1", model="test/model",
                    quiet_mode=True, skip_context_files=True, skip_memory=True)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._fire_stream_delta = lambda text: None
    return agent


def _stream(broken_args: str, finish_reason: str):
    def _gen():
        yield _make_stream_chunk(tool_calls=[_make_tool_call_delta(index=0, tc_id="call_1", name="write_file")])
        yield _make_stream_chunk(tool_calls=[_make_tool_call_delta(index=0, arguments=broken_args)])
        yield _make_stream_chunk(finish_reason=finish_reason)
    return _gen


def _run_stream(broken_args: str, finish_reason: str):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = lambda *a, **kw: _stream(broken_args, finish_reason)()
    with patch("run_agent.AIAgent._create_request_openai_client", return_value=mock_client), \
         patch("run_agent.AIAgent._close_request_openai_client"):
        return _make_agent()._interruptible_streaming_api_call({})


def test_provider_stop_with_unparseable_args_is_tagged_not_blamed_on_output_cap():
    response = _run_stream(_BROKEN_ARGS, "tool_calls")

    assert response.choices[0].finish_reason == "length", (
        "the broken call must stay on the length path so it is never executed"
    )
    assert getattr(response, "_malformed_tool_args", False) is True
    assert response.choices[0].message.tool_calls[0].function.arguments == _BROKEN_ARGS


def test_real_length_stop_is_not_tagged_malformed():
    response = _run_stream(_BROKEN_ARGS, "length")

    assert response.choices[0].finish_reason == "length"
    assert getattr(response, "_malformed_tool_args", False) is False, (
        "a provider-reported length stop IS an output cap and keeps the max_tokens ladder"
    )


# ── truncation handler ───────────────────────────────────────────────────────

class _FakeAgent:
    log_prefix = "[test] "
    provider = "custom"

    def __init__(self):
        self._ephemeral_max_output_tokens = None
        self.buffered: list[str] = []
        self.printed: list[str] = []
        self.cleaned: list[str] = []
        self.persisted = None

    def _buffer_vprint(self, message, **_kw):
        self.buffered.append(message)

    def _flush_status_buffer(self):
        pass

    def _vprint(self, message, **_kw):
        self.printed.append(message)

    def _cleanup_task_resources(self, task_id):
        self.cleaned.append(task_id)

    def _persist_session(self, messages, history):
        self.persisted = (list(messages), history)


def _make_st(agent, response):
    return _Trunc(
        agent=agent, response=response, finish_reason="length", conversation_history=[],
        api_call_count=1, effective_task_id="task-1", current_turn_user_idx=0,
        messages=[
            {"role": "user", "content": "write the file"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "write_file", "arguments": _BROKEN_ARGS}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ],
        length_continue_retries=0, truncated_response_parts=[], truncated_tool_call_retries=0,
        retry_count=0, compression_attempts=0,
    )


def _malformed_response():
    response = SimpleNamespace(id="stream-1", model="m", usage=None,
                               choices=[SimpleNamespace(index=0, message=SimpleNamespace(content=None), finish_reason="length")])
    response._malformed_tool_args = True
    return response


def test_malformed_tool_call_retries_plainly_without_boosting_max_tokens():
    agent = _FakeAgent()
    st = _make_st(agent, _malformed_response())

    verdict = _retry_malformed_tool_call(st)

    assert verdict.action == "continue"
    assert st.truncated_tool_call_retries == 1
    assert agent._ephemeral_max_output_tokens is None, (
        "the provider never applied an output cap, so a doubled max_tokens cannot help"
    )
    assert any("not valid JSON" in line for line in agent.buffered)


def test_malformed_tool_call_gives_up_with_accurate_copy():
    agent = _FakeAgent()
    st = _make_st(agent, _malformed_response())
    st.truncated_tool_call_retries = _MALFORMED_TOOL_CALL_RETRIES

    verdict = _retry_malformed_tool_call(st)

    assert verdict.action == "return"
    result = verdict.result
    assert result["failure_reason"] == "truncated"
    assert result["failure_retryable"] is True
    assert "not valid JSON" in result["final_response"]
    assert "raising max_tokens won't help" in result["final_response"]
    assert result["final_response"] == site_copy("malformed_tool_call")
    assert result["messages"][-1]["role"] == "assistant", "the transcript must not end on a tool result"
    assert agent.cleaned == ["task-1"]
