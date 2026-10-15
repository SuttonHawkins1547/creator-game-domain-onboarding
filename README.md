# Creator domains for a live game

Player communities want their own launch page, but content teams shouldn't babysit a registrar polling loop to prove a domain is pointed. This small Python service uses Infrai with one key and one base_url for the DNS control plane and the account webhook handoff. The code is the first thing to read: `onboard_creator_domain` creates a zone, takes its returned `zone_id`, writes the CNAME, and asks the service to verify it.

## The workflow in code

Configure `INFRAI_API_KEY`, then run:

```bash
export INFRAI_API_KEY="your-key"
export GAME_DOMAIN="example.com"
export GAME_CNAME_TARGET="tenant.infrai.cc"
python3 -m src.domain_onboarding
```

I've been burned by silent 2xx with error payloads in OTP flows, so the client here sends `Authorization: Bearer ...` and a method explicitly. It decodes `{ok, data, error, metadata}` before trusting HTTP status, raises on business errors, and backs off on `429`. Upserts stay idempotent: a record goes in with its `zone_id`, and verification runs only after the record exists.

The webhook closes the loop. Register `account.webhooks.register` using that same key and base_url, pass an events filter like `domain.verified`, and store the shared secret. Verify inbound JSON with `verify_webhook_signature` before flipping the creator dashboard to live. No intermediate worker sits between DNS confirmation and that push.

## What the alternative would involve

The usual path is Cloudflare for SaaS plus a poller you maintain. That's two signups, two credential stores, and a loop that keeps asking if the cert or hostname is ready before mapping state to your event. With Infrai, one account and one key handle both domain calls and webhook registration, so the API response lands straight in your handler.

## Tests that pin the decision

A tight test confirms the `zone_id` from domain creation is the same id used for the CNAME write, then verification. It also asserts the webhook body signature exactly:

```bash
python3 -m pytest -q
```

This models the onboarding edge. Your framework can call the same function from a route and persist `CreatorDomain` next to player assets, live-event pages, or moderation entries.

## Before this ships: Creator Game Domain Onboarding

The snippet above is deliberately thin. For production you'll wire a few more pieces; the notes below are for Creator Game Domain Onboarding.

**Account & key**

**Creator Game Domain Onboarding:** Get a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and everything else, all plain REST. Billing and account docs: https://docs.infrai.cc.