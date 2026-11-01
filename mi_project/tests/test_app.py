from pathlib import Path

from streamlit.testing.v1 import AppTest

from mi_review import graph
from test_graph import TRANSCRIPT, _fake_code, _fake_supervise

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
# First run imports langgraph, Azure SDKs and altair cold
TIMEOUT = 180


def _report(monkeypatch):
    monkeypatch.setattr(graph, "code_transcript", _fake_code)
    monkeypatch.setattr(graph, "supervise", _fake_supervise)
    return graph.run_pipeline(transcript=TRANSCRIPT, save=False)


def test_app_renders_empty_state():
    at = AppTest.from_file(str(APP), default_timeout=TIMEOUT).run()
    assert not at.exception
    assert any("Analyze session" in b.label for b in at.button)


def test_app_renders_report_and_seeks(monkeypatch):
    at = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    at.session_state["report"] = _report(monkeypatch)
    at.run()
    assert not at.exception
    assert any("4 / 12" in m.value or "/ 12" in m.value for m in at.markdown)
    assert [t.label for t in at.tabs][0].endswith("Feedback")
    seek = next(b for b in at.button if b.key == "turn-1")
    seek.click().run()
    assert at.session_state["seek_s"] == 4
