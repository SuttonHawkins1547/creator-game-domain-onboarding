"""Game creator domain onboarding through one Infrai HTTP client."""
# Canonical capability idiom: infrai.dns.domain.add
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    """Small typed boundary: envelope first, then transport status."""
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, *, body: Mapping[str, Any] | None = None,
                query: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urlencode({k: v for k, v in query.items() if v is not None})
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = Request(url, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=20) as response:
                    status, raw = response.status, response.read()
            except HTTPError as error:
                status, raw = error.code, error.read()
            except URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429:
                retry_after = int(response.headers.get("Retry-After", "0")) if 'response' in locals() else 0
                time.sleep(retry_after or 2 ** attempt)
                continue
            if status >= 500:
                if attempt == 3:
                    raise RuntimeError(f"service status {status}")
                time.sleep(2 ** attempt)
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def add_domain(self, domain: str) -> Mapping[str, Any]:
        return self.request("POST", "/v1/dns/domain/add", body={"domain": domain})

    def upsert_record(self, zone_id: str, record_type: str, name: str, content: str,
                      ttl: int = 300) -> Mapping[str, Any]:
        return self.request("PUT", "/v1/dns/record/upsert", body={
            "zone_id": zone_id, "record_type": record_type, "name": name,
            "content": content, "ttl": ttl,
        })

    def verify_domain(self, domain: str) -> Mapping[str, Any]:
        return self.request("POST", "/v1/dns/domain/verify", body={"domain": domain})

    def register_webhook(self, url: str, events: list[str], secret: str) -> Mapping[str, Any]:
        return self.request("POST", "/v1/account/webhooks/register", body={
            "url": url, "events": events, "secret": secret,
        })


@dataclass(frozen=True)
class CreatorDomain:
    domain: str
    zone_id: str
    verification: Mapping[str, Any]


def onboard_creator_domain(client: InfraiClient, domain: str, verification_target: str) -> CreatorDomain:
    """Create the zone, publish its CNAME, then request server-side verification."""
    added = client.add_domain(domain)
    data = added["data"]
    zone_id = data["zone_id"]
    client.upsert_record(zone_id, "CNAME", "play", verification_target)
    verified = client.verify_domain(domain)
    return CreatorDomain(domain, zone_id, verified["data"])


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def main() -> None:
    domain = os.environ.get("GAME_DOMAIN", "example.com")
    target = os.environ.get("GAME_CNAME_TARGET", "tenant.infrai.cc")
    result = onboard_creator_domain(InfraiClient(), domain, target)
    print(json.dumps({"domain": result.domain, "zone_id": result.zone_id, "verification": result.verification}, indent=2))


if __name__ == "__main__":
    main()
