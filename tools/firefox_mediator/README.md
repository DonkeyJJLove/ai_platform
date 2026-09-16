# LION Firefox Project Mediator

Canonical browser-mediated transport for the LION control plane.

`open_session_mediator.ps1` drives an **existing authenticated Firefox Developer Edition session** through Windows UI Automation. Login, MFA and CAPTCHA remain human gates. The mediator is bound to the `LION_EVOLUSION` ChatGPT project and creates a new project conversation per broker request. It never exports cookies, passwords or ChatGPT session tokens.

The Mission Control relay in `tools/lion_firefox_broker_relay.py` retains `saas-mediator.key` and broker response tokens inside LION-AUTH-LAB. The Windows mediator receives only non-secret work items and writes only answer envelopes back to the IPC directory.

## Exactly-once recovery

Before Send, the mediator snapshots project conversations. Immediately after invoking Send it persists `SEND_TRIGGERED`. If the browser does not immediately navigate to the new `/c/...` URL, it recovers the new project conversation from the visible project conversation list, opens it and binds its URL. On restart, `SEND_TRIGGERED` without a conversation URL is recovered the same way and is **never resent**.

The runtime is not READY merely because a stale status file exists. Supervisor currentness must be based on a live mediator process plus a fresh status observation.
