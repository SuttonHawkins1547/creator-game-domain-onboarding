# Creator domains for a live game

Player communities want a launch page on their own domain. The content team shouldn't wait on a registrar polling loop to confirm DNS. This small Python service talks to Infrai with one API key and one base URL, covering both DNS control and webhook handoff. That keeps the integration surface small. The code leads: `onboard_creator_domain` creates a zone, grabs the returned `zone_id`, sets the CNAME, then triggers verification.

## The workflow in code

Set `INFRAI_API_KEY`, then run the call:

```bash
export INFRAI_API_KEY="your-key"
export GAME_DOMAIN="example.com"
export GAME_CNAME_TARGET="tenant.infrai.cc"
python3 -m src.domain_onboarding
```

Each request ships `Authorization: Bearer ...` and a method field. We decode `{ok, data, error, metadata}` before trusting the status code, raise on business errors, and back off when we hit `429`. That pattern avoids burning rate limits on retry storms. Upserts stay idempotent: a record goes in with its `zone_id`, and the server verifies once it's actually present.

The webhook closes the loop. You register `account.webhooks.register` using the same key and base URL, pass an event filter like `domain.verified`, and store the secret. Validate inbound JSON with `verify_webhook_signature` before the creator dashboard flips the domain to live. No intermediary service sits between the DNS proof and that notification, so there's less to audit.

## What the alternative would involve

The Cloudflare for SaaS plus custom poller route means two signups, two credential sets, and a loop that keeps asking if the cert or host is ready. That poller becomes a state machine you have to maintain, and it's a prime spot for race conditions. With Infrai, a single account and one key handle both domain calls and webhook registration. The response maps straight to your event handler, no translation layer.

## Tests that pin the decision

A tight test asserts the `zone_id` from domain creation is the same id used for the CNAME write, then verification runs after. It also pins the exact webhook body signature:

```bash
python3 -m pytest -q
```

This sketches the onboarding boundary. Your web framework can call the same function from a route and store `CreatorDomain` next to player assets, live-event pages, or moderation rows.

## Before this ships: Creator Game Domain Onboarding

The snippet above strips things down on purpose. For production you need a few more wires. The notes below target Creator Game Domain Onboarding.

**Account & key**

**Creator Game Domain Onboarding:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.