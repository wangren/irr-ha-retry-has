# DMR HA Retry HAS — Open Issues

Tracked open questions and risks to close before architecture signoff. File
updates as tracker items per HAS convention.

| ID | Title | Severity | Owner | Notes |
|----|-------|----------|-------|-------|
| OI-1 | Congestion modeling / real retry rate | High | — | Measure retry rate under realistic (not worst-case) load; confirm the ~2× reissue throughput tax is acceptable. Weakest of the four benefit arguments. |
| OI-2 | Grant loss / timeout reconciliation | High | — | A lost `HR_Grant` must not deadlock a source forever. Define timeout or reconciliation handshake. Robustness/correctness. |
| OI-3 | Fabric-internal congestion | Medium | — | Endpoint retry does not resolve congestion arising *inside* the fabric (only endpoints trigger retry). Determine whether a complementary mechanism is needed. |
| OI-4 | Realistic topology counter count | Medium | — | Replace the 64×64×8 worst-case estimate with real HA/CA fanout per instance; size per-source occupancy vectors accordingly. |
| OI-5 | Hysteresis thresholds & anti-oscillation | High | — | Define upper (early-retry) and lower (exit) occupancy thresholds; prove no oscillation and guaranteed exit from retry regime (§7.2). |
| OI-6 | VC-by-VC retryability audit | High | — | Enumerate which VCs/message classes can be *fully* retryable (all-or-nothing per VC). Gates the VC-invisibility / dedicated-buffering benefit. |
| OI-7 | Unify with existing HAMVF retry precedents | Medium | — | Reconcile with HAMVF early-completion (§8.10.23) and DRS/NDR trash-and-retry deadlock breaker (§8.10.28.1) — extend or keep separate. |
| OI-8 | Per-cycle retry-decision logic cost | Medium | — | Size the N/cycle admission logic + per-source comparators (the real cost driver, not counter storage). |
| OI-9 | Data-message retry buffering | Medium | — | Confirm retained-data buffering bound (§7.3) and re-fetch vs. retain tradeoff for retryable write/WB data. |
| OI-10 | Push-to-pull scenario detail | Low | Thibaut | Capture the specific protocol-interop deadlock scenario Thibaut offered to elaborate; it is the strongest justification for retryable data. |
