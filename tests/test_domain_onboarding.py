import json

from src.domain_onboarding import CreatorDomain, onboard_creator_domain, verify_webhook_signature


class FakeClient:
    def __init__(self):
        self.calls = []

    def add_domain(self, domain):
        self.calls.append(("add", domain))
        return {"ok": True, "data": {"zone_id": "zone_42"}}

    def upsert_record(self, zone_id, record_type, name, content):
        self.calls.append(("record", zone_id, record_type, name, content))
        return {"ok": True, "data": {"record_id": "rec_1"}}

    def verify_domain(self, domain):
        self.calls.append(("verify", domain))
        return {"ok": True, "data": {"status": "verified"}}


def test_onboarding_uses_returned_zone_before_writing_record():
    client = FakeClient()
    result = onboard_creator_domain(client, "creator.game", "tenant.infrai.cc")
    assert isinstance(result, CreatorDomain)
    assert client.calls == [
        ("add", "creator.game"),
        ("record", "zone_42", "CNAME", "play", "tenant.infrai.cc"),
        ("verify", "creator.game"),
    ]


def test_webhook_signature_accepts_exact_body():
    body = json.dumps({"event": "domain.verified"}).encode()
    import hashlib, hmac
    signature = hmac.new(b"creator-secret", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, signature, "creator-secret")
    assert not verify_webhook_signature(body + b"!", signature, "creator-secret")
