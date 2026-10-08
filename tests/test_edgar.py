import httpx
import pytest

from filing_delta import edgar
from filing_delta.edgar import Edgar


def client(seen):
    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b'{"ok": 1}')

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_sends_user_agent_then_serves_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test Agent test@example.com")
    monkeypatch.setattr(edgar, "MIN_INTERVAL", 0.0)
    seen = []
    e = Edgar(tmp_path, client(seen))
    assert e.submissions(27904) == {"ok": 1}
    assert e.submissions(27904) == {"ok": 1}
    assert len(seen) == 1
    assert seen[0].headers["User-Agent"] == "Test Agent test@example.com"
    assert (tmp_path / "submissions_CIK0000027904.json").exists()


def test_missing_user_agent_refuses_to_fetch(tmp_path, monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    seen = []
    with pytest.raises(RuntimeError):
        Edgar(tmp_path, client(seen)).submissions(1)
    assert seen == []
