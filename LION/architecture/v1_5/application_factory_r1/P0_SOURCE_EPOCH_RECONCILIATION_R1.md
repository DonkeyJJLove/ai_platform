# PR #427 — P0 historical source epoch versus current effect inventory

Status: `SOURCE_TEST_RECONCILIATION_CANDIDATE`. No runtime admission, deployment or authority effect.

The P0 MOON attested campaign is historical evidence. Its pinned source is:

```text
repository: DonkeyJJLove/ai_platform
HEAD: b6cc132095deb268b2754d2afc0634aeac5a7ac4
TREE: 7f6a2bbb2efa6551340b24873ea3e21f5205ee95
scan_digest: eeb9ec6f043c9e454999aee2f02c3ee42d65878eee0a5d8015e752e887f11173
effect surfaces: 567
taxonomy unresolved: 0
```

The P0 campaign must **never** silently accept a new scan digest or claim that past bypass evidence covers new source. The original 25-test P0 sample passed against this exact master source epoch.

The proposed `cyber_lion/tests/p0_historical_inventory.py` reconstructs the historical source from exact local Git object bytes, verifies the pinned HEAD/TREE and each source blob, and asserts the original scan digest and taxonomy. Nine existing P0 tests use this historical inventory; the one P0 security-boundary test additionally uses a disposable exact historical checkout, because its evidence owner checks the Git HEAD/TREE of the actual source directory. Missing or substituted historical objects fail closed. No Git ref is modified and no network fetch is performed.

**A separate current-candidate test remains mandatory.** On PR #427 candidate `59301240008e528fc5e511f277bfc15fb5ff0c44`, current inventory evidence was:

```text
TREE: 6620c8069c8efbc67e63e34b30ec2448c27c3a47
current scan digest: 1ad30f78aabd356498b7326cdbb719530c38c2ee06ae8575478948af7439c36b
surfaces: 573
unchanged from historical: 562
added: 11
removed/replaced: 5
unresolved taxonomy: 0
```

The 11 new surfaces are source-observed `persistent_state.write` calls with `local_write` classification: six in `cooperative_runtime_preparation_provider.py` and five in `control_plane_reconnaissance.py`. The five replaced surface identities are in the latter owner. The seven historical certified P0 surface digests remain present in the candidate. None of these facts promotes the historical seven's evidence to new current-run authorization, mediation or closure.

Evidence is deliberately separated:

```text
P0 historical proof and receipts (SOURCE_HEAD=b6cc132, SCAN=eeb9...)
                !=
current candidate effect inventory (HEAD=5930124, SCAN=1ad30...)
```

The work changes test-source selection only, plus one independent current-candidate inventory test and fail-closed history-binding tests. The main P0 production mediation and attestation machinery is not changed. Further changes to production source invalidate the current candidate counts and require an explicit new scan/reconciliation, not the reuse of this snapshot.

**This increment does not close `STALE_EXACT_CURRENTNESS_CARRIER` or `TRUTH_PLANE_MISMATCH`.** Truth subject/currentness carriers are a separate final step after source and peer review. Likewise, the historical P0 test pass is not a claim that newly introduced effects have passed new independent runtime falsification.

Machine-readable current-candidate delta evidence is saved outside the repo at `/srv/lion-e4-candidate-r1/outputs/PR427_P0_INVENTORY_DELTA_20261008.json`.
