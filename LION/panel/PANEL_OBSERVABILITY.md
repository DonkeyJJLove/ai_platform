# Panel observability

The panel should expose state from independently owned evidence planes instead of maintaining parallel truth.

Minimum observable dimensions:

- source/runtime identity;
- mission and phase identity;
- currentness/freshness;
- model provider/transport/call state;
- operator command identity;
- authority decision and expiry where relevant;
- runtime admission;
- effect receipt;
- independent effect observation;
- reconciliation result;
- transport errors and renderer diagnostics.

UI diagnostics are useful evidence about the UI itself but are not authority or external-effect evidence.

Live deployment claims require runtime reacquisition. Source documentation alone can only establish source-bound behavior.
