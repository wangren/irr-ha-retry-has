# IRR HA Retry — Hardware Architecture Specification

**Document:** IRR_HA_retry
**Revision:** 0.1 (DRAFT — for discussion, not approved architecture)
**Date:** 2026-09-17
**Scope:** End-to-end retry-based flow control for Home Agent (HA) traffic on IRR

---

## 1. Introduction & Conventions

### 1.1 Purpose

This document specifies an **end-to-end (E2E) retry-based flow-control**
architecture for Home Agent traffic on Iron Rapids (IRR). It defines the
responsibilities of the three participating agent classes — the **Core**
(Requester / Caching Agent, CA), the **Fabric** (NIP-based interconnect), and
the **Home Agent** (HA, as implemented by the HAMVF IP) — and the messages,
counters, and state machines needed to realize retry as an alternative and
complement to credit-based backpressure.

Retry allows a target that cannot currently accept a request to *reject* it
("retry it") rather than buffer it in the interconnect. The rejected request is
drained from the fabric and later reissued by the source once the target signals
it is ready. This trades interconnect buffering/pressure for endpoint tracking
complexity.

### 1.2 Rationale (why retry)

1. **Interconnect pressure reduction.** Retryable messages are drained from the
   interconnect; their VC becomes "invisible" to the interconnect, enabling
   simpler dedicated per-VC buffering (cf. adaptive buffering / VNA in UPI/UXI
   links). This is **all-or-nothing per VC**: a single non-retryable message
   class keeps the whole VC visible.
2. **Congestion clog minimization.** Messages participating in a congestion
   event are not held in the fabric for long, preserving fabric availability.
   Cost: retried messages are issued twice (≈2× throughput for retried traffic).
3. **Push-to-pull deadlock avoidance.** Retry maximizes interoperability between
   push- and pull-style protocols; this is the primary justification for making
   *data* messages retryable despite the buffering cost.
4. **Fine-grain, scalable E2E QoS.** Per-source(+VC) occupancy tracking enables
   selective throttling and anti-starvation — the primary motivation for this
   specification.

### 1.3 Relationship to CHI E2E

This architecture borrows the **grant-gated retry** discipline of ARM AMBA CHI's
end-to-end flow control. The mapping is summarized in §6 and cross-referenced
throughout. Where a CHI primitive maps cleanly, the CHI name is cited. Where IRR
needs behavior CHI does not express, a **new** IRR name is introduced and its
nearest CHI relative is noted explicitly.

### 1.4 Terminology

| Term | Meaning |
|------|---------|
| CA / Requester | Caching Agent issuing requests (the "source"). Core-side. |
| HA | Home Agent (HAMVF IP) servicing requests (the "target"). |
| Fabric / NIP | On-die interconnect carrying messages (NIP 2.0, no BRIDGE IP for HAMVF). |
| VC | Virtual Channel (independent flow-control/ordering domain). |
| Retryable message | A message the target may reject; source retains reissue state. |
| Grant | Target→source signal authorizing reissue of a retried message (see §4.3). |
| Occupancy | Count of outstanding transactions from a source at a target. |

### 1.5 Conventions

- Spec issues are filed as tracker items, not inline comments (per HAS convention).
- **New IRR message/signal names are prefixed `HR_`** (HA-Retry) to distinguish
  them from inherited UXI/NIP/CHI names.
- Requirement keywords (**shall**, **should**, **may**) follow RFC 2119 intent.

---

## 2. Architectural Overview

### 2.1 Retry lifecycle (happy path)

```
  CA (Core)                Fabric (NIP)                 HA (HAMVF)
     |                          |                            |
     |  1. Request (speculative)|                            |
     |------------------------->|--------------------------->|
     |                          |          2. Cannot accept  |
     |                          |             (no resource / |
     |                          |              QoS throttle) |
     |   3. HR_RetryAck(PoolID) |                            |
     |<-------------------------|<---------------------------|
     |  (drop req from fabric;  |                            |
     |   retain tracker;        |                            |
     |   mark "retry expected") |                            |
     |                          |                            |
     |         ... time passes; congestion clears ...        |
     |                          |                            |
     |   4. HR_Grant(PoolID)    |                            |
     |<-------------------------|<---------------------------|
     |                          |                            |
     |  5. Reissue Request      |                            |
     |------------------------->|--------------------------->|
     |                          |            6. Accept, proc |
     |   7. Cmp* / Data         |                            |
     |<-------------------------|<---------------------------|
```

### 2.2 Key principles

- **P1 — Grant-gated reissue.** A retried request **shall not** be reissued
  until the source receives an explicit `HR_Grant` for its pool. The source
  **shall not** spin-retry. (Mirrors CHI RetryAck→PCrdGrant→reissue.)
- **P2 — Per-VC independence.** Retry accounting is maintained per
  `{peer, VC}`; congestion in one VC **shall not** trip another VC's retry
  decision.
- **P3 — Bounded reissue.** Outstanding reissues from a source are bounded by
  the number of grants the target has emitted, so the target paces recovery.
- **P4 — Guaranteed exit.** The system **shall** provably return to non-retry
  operation after congestion clears (no permanent retry regime — see §7).
- **P5 — Occupancy-based QoS.** The retry/accept decision **may** use per-source
  occupancy and message priority to enforce fairness and anti-starvation (§5).

---

## 3. Agent Responsibilities

### 3.1 Core (Requester / Caching Agent) — what must change

The Core-side CA already tracks outstanding requests in its request tracker. The
retry feature adds:

**3.1.1 Speculative issue.** The CA **may** issue a request without holding a
pre-allocated target credit (unlike a pure credit scheme). Related CHI behavior:
CHI Requesters may send without a P-Credit and handle RetryAck.

**3.1.2 Retry-aware tracker retention.** On receiving `HR_RetryAck` for an
outstanding request, the CA **shall**:
- retain the request's tracker entry and all reissue state (address, opcode,
  VC, and the returned `PoolID`);
- treat the request as *not in fabric* (drained) but *not complete*;
- set the per-target `retry-expected` accounting (§5.1).

**3.1.3 Grant-gated reissue.** On receiving `HR_Grant(PoolID)`, the CA **shall**
reissue exactly one retried request matching that pool. If the CA has multiple
retried requests for the pool, selection **should** be age-ordered to bound
latency and prevent starvation.

**3.1.4 Grant/credit reconciliation.** Because grants and normal credit returns
may arrive out of order relative to retries (§4.4), the CA **shall** maintain the
counters of §5.1 to reconcile "grant received but retry not yet reissued" vs.
"retry outstanding but grant not yet received."

**3.1.5 Data-message retry (optional, push-to-pull).** For retryable *data*
(write/WB) messages, the CA **shall** retain the data payload (or a re-fetchable
handle) until the grant-gated reissue completes. Buffering cost is bounded and
comparable to a pull protocol's (see §7.3). Related CHI: write retry with
DataPull-style semantics; **IRR extends** this to arbitrary data VCs.

### 3.2 Fabric (NIP interconnect) — what must do

The NIP fabric is **not** the retry decision-maker; retry is an endpoint (CA/HA)
function. The fabric's obligations:

**3.2.1 Retryable-VC transport.** The fabric **shall** carry `HR_RetryAck` and
`HR_Grant` as response-class messages routable from HA back to the originating
CA, using existing NIP response routing (HNID/HTID-style, cf. HAMVF §8.10.7).

**3.2.2 Draining, not buffering.** When a request is retried, the fabric holds no
residual state — the request has already been delivered to the HA and
`HR_RetryAck` returned. The fabric **shall not** be required to replay or buffer
retried requests. This is the source of the interconnect-pressure benefit (§1.2).

**3.2.3 Retryable-VC invisibility (optimization).** For VCs in which *all*
message classes are retryable, the fabric **may** reduce shared adaptive buffering
to dedicated per-VC buffering (§1.2 benefit 1). The fabric **shall** expose which
VCs qualify via configuration; mixing a non-retryable class into such a VC is a
misconfiguration (§8).

**3.2.4 No new ordering guarantees required.** The fabric **shall not** be
required to order `HR_Grant` relative to credit returns; reconciliation is an
endpoint responsibility (§3.1.4, §4.4). This keeps fabric changes minimal.

**3.2.5 Congestion-internal caveat.** Retry addresses endpoint-induced
congestion. Congestion *inside* the fabric is not resolved by this mechanism
(only endpoints trigger retry); see open issue OI-3.

### 3.3 Home Agent (HAMVF) — what must do

The HA is the retry **decision point** and the grant **issuer**.

**3.3.1 Retry-decision logic (high throughput).** On each incoming request the HA
**shall** decide accept vs. retry. This decision **should** operate at up to the
peak arrival rate (N/cycle), which may exceed the HA's processing rate (1/cycle),
so the fabric can be drained faster than steady-state processing (§1.2 benefit 2).
Related HAMVF context: early-completion response generation (HAMVF §8.10.23) and
the existing "trash-and-retry" DRS/NDR deadlock breaker (HAMVF §8.10.28.1), which
is a narrow precedent for HA-initiated retry.

**3.3.2 Retry causes.** The HA **shall** retry a request when any of:
- no free tracker/resource in the target pool (resource exhaustion);
- per-source occupancy exceeds its QoS cap (§5.2) — *early retry*;
- forced retry for deadlock/livelock avoidance (§7).

**3.3.3 Pool identification.** Each `HR_RetryAck` **shall** carry a `PoolID`
identifying which resource pool the source must be granted before reissue.
Related CHI: `PCrdType`. **IRR difference:** pools **may** be defined per
`{resource-class, VC}` rather than CHI's per-transaction-class only (§6).

**3.3.4 Grant generation.** When a pooled resource becomes available the HA
**shall** emit `HR_Grant(PoolID)` to a source with an outstanding retry for that
pool. Grant issuance order across waiting sources **shall** be arbitrated for
fairness/anti-starvation (round-robin or priority-weighted; §5.2). Related CHI:
`PCrdGrant`.

**3.3.5 Occupancy & reconciliation counters.** The HA **shall** maintain the
per-source(+VC) counters of §5.2, including the aggregate pooled-resource
counter that gates *whether* any request can be accepted, plus the per-source
occupancy that gates *which* source is admitted/throttled.

**3.3.6 Livelock exit.** The HA **shall** implement the anti-livelock mechanism
of §7 guaranteeing eventual return to non-retry operation.

**3.3.7 Grant loss / robustness.** A lost `HR_Grant` must not deadlock a source
forever. The HA **shall** support a reconciliation/timeout path (see OI-2).

---

## 4. Messages

New IRR messages are prefixed `HR_`. Each entry notes its nearest CHI relative.

### 4.1 HR_RetryAck (HA → CA)

- **Purpose:** reject an accepted-but-not-serviceable request; instruct source to
  retain reissue state and await a grant.
- **Fields:** target transaction handle (to identify the retried request at the
  source), `PoolID`, VC.
- **CHI relative:** `RetryAck` (response with `PCrdType`). **IRR change:** `PoolID`
  granularity may include VC.

### 4.2 (reuse) Request / Reissue (CA → HA)

- Reissue uses the **same** request encoding as the original request; no new
  opcode is required. A reissued request **may** set a 1-bit `HR_Reissue` hint so
  the HA can distinguish first-issue from reissue for telemetry (optional).
- **CHI relative:** reissued request after PCrdGrant (no distinct opcode in CHI
  either). The `HR_Reissue` hint has **no CHI equivalent** (IRR telemetry aid).

### 4.3 HR_Grant (HA → CA)

- **Purpose:** authorize the source to reissue exactly one retried request for the
  named pool.
- **Fields:** `PoolID`, VC, grant count (default 1; batched grants optional).
- **CHI relative:** `PCrdGrant`. **IRR change:** optional batched grant-count has
  no direct CHI single-grant equivalent (CHI grants one credit per PCrdGrant).

### 4.4 Ordering note

`HR_Grant` and normal credit/completion returns travel on response paths and
**may** arrive at the source in either order relative to a preceding
`HR_RetryAck`. Sources reconcile via §5.1 counters. This is the same hazard
Thibaut flagged ("credit returns may bypass retries"). CHI avoids some of this by
tighter channel rules; **IRR chooses** endpoint reconciliation to keep the fabric
unchanged (§3.2.4).

---

## 5. Counters & Tracking

This section defines the tracking state. The full `{source, target, VC} × 3`
matrix is the theoretical maximum; §5.3 gives the recommended reduced form.

### 5.1 Source-side counters (per `{target, VC}`)

Up to three counters, per Thibaut's model:

1. **Credits expected** (`N−P`): source received N retries but is still missing P
   credits (N>P). Eliminable if the implementation guarantees retries always
   arrive before their associated credits.
2. **Retry expected** (`P−N`): source received P credits but is still missing N
   retries (P>N) — possible because credit returns may bypass retries (§4.4).
3. **Credits stocked** (`P`): credits received but not yet acted upon. Eliminable
   if the source always acts on a credit immediately.

### 5.2 Target-side (HA) counters (per `{source, VC}`)

1. **Credits expected** (`M−P`): HA retried M messages but returned only P credits.
2. **Retry expected** (`P−R`): HA returned P credits but received only R reissues.
   Critical for declaring "back to normal" (no reissue still in flight).
3. **Total ongoing** (`M`): outstanding transactions from this source. **This is
   the QoS/throttle counter** — combined with message priority it drives the
   early-retry decision (§3.3.2). *CHI relative:* per-Requester outstanding
   tracking behind the HN.

Plus **one (or few) aggregate pooled-resource counter(s)** per resource type:
the physical "free trackers" gate that decides whether *any* request can be
accepted (see §5.3 rationale).

### 5.3 Recommended reduced tracking (cost)

Full matrix worst case (illustrative): 64 sources × 64 targets × 8 VC × 3
counters ≈ 192k counters, ≈576 kB of counter storage chip-wide — dominated by
the source×target cross-product and the ×8 VC and ×3 multipliers.

**Recommendation:** do **not** instantiate the full cross-product. Instead, at
each HA instance keep:

- **Aggregate pooled-resource counter(s)** — answers "do I have room at all"
  (physical constraint). A handful per resource class.
- **Per-source occupancy vector** (`Total ongoing`, optionally per-VC) — answers
  "who is admitted / who to throttle" (fairness/attribution). At one HA this is
  O(sources), e.g. 64 counters ≈ 64–192 B per instance; ~0.5–2.3 kB chip-wide
  across ~8–12 HA instances — 2–3 orders of magnitude below the full matrix.
- **Reconciliation counters** (`Credits expected` / `Retry expected`) **only if**
  ordering guarantees of §5.1/§5.2 cannot be met; otherwise omit.

The aggregate counter and the per-source vector are **not redundant**: the former
gates capacity, the latter gates *selective* admission/QoS. Dropping the
per-source dimension would leave a scheme that can detect congestion but cannot
act selectively — forfeiting the QoS goal (§1.2 benefit 4).

### 5.4 Cost driver is logic, not storage

Storage is negligible at IRR throughput. The real cost is per-cycle logic:
multi-increment/decrement saturating counters with arbitration (if multiple
retries/completions per source per cycle) and per-source threshold comparators
evaluated combinationally to sustain the N/cycle retry-decision rate (§3.3.1).

---

## 6. CHI E2E Mapping Summary

| IRR concept | Nearest CHI primitive | Difference / why new |
|-------------|----------------------|----------------------|
| `HR_RetryAck` | `RetryAck` (+`PCrdType`) | `PoolID` may include VC granularity |
| `HR_Grant` | `PCrdGrant` | Optional batched grant-count |
| Reissue request | Post-PCrdGrant reissue | Same opcode; optional `HR_Reissue` hint (no CHI equiv.) |
| `PoolID` | `PCrdType` | Per-`{resource-class,VC}`, not per-transaction-class only |
| Per-source occupancy | Per-Requester outstanding @ HN | Explicit QoS/early-retry use |
| Grant-gated reissue (P1) | RetryAck→PCrdGrant discipline | Adopted directly (livelock-safe) |
| Endpoint reconciliation (§4.4) | CHI channel ordering rules | IRR moves it to endpoints to keep fabric unchanged |
| Retryable data messages (§3.1.5) | Write retry / DataPull | Generalized to arbitrary data VCs (push-to-pull) |

**Key adopted idea:** CHI's retry is **credit-grant-gated, not spin-based** — the
source reissues only after `PCrdGrant`. This directly addresses the "stuck in
retry regime" livelock risk (§7) and is the main reason to model on CHI E2E rather
than inventing a blind-retry scheme.

---

## 7. Deadlock, Livelock & the Retry Regime

### 7.1 Push-to-pull deadlock

Retry maximizes push/pull protocol interoperability. Making data messages
retryable (§3.1.5) is what resolves the classic push-to-pull dependency: a pushed
data message that cannot be sunk is retried and later grant-gated, rather than
holding fabric buffering hostage. This is treated as a **correctness** benefit,
not merely performance.

### 7.2 Stuck-in-retry (livelock) — primary risk

Once retry triggers (possibly forced by resource exhaustion), the system must
**provably** return to non-retry operation. Risk: a self-sustaining regime where
everything is retried even after congestion clears, paying ≈2× latency/throughput
indefinitely — a hazard plain backpressure does **not** incur.

**Mitigation (grant-gated, from CHI):** because reissue is gated by `HR_Grant`
(P1/P3), the HA controls the reissue rate. The HA **shall** guarantee forward
progress by:

- issuing grants in bounded time once resources free (no indefinite withholding);
- fair grant arbitration so no source is starved of grants;
- a **hysteresis exit condition**: once per-source occupancy and pooled-resource
  counters fall below a *lower* threshold (distinct from the *upper* early-retry
  threshold), the HA **shall** stop issuing early (QoS) retries and accept
  first-issue requests directly — returning to non-retry steady state.

Hysteresis (two thresholds) prevents oscillation between retry and non-retry.

### 7.3 Data buffering scalability

Retained data for retryable data messages (§3.1.5) is bounded by the number of
outstanding retryable data transactions per source, which is itself bounded by
occupancy caps (§5.2). Thus data buffering is **scalable** and no worse than a
pull protocol's inherent buffering.

---

## 8. Configuration & Misconfiguration Hazards

- **Retryable-VC declaration.** Config **shall** mark which VCs are fully
  retryable (all classes). Placing a non-retryable class in a "retryable" VC
  breaks VC-invisibility (§3.2.3) — undefined performance behavior.
- **Threshold programming.** Upper (early-retry) and lower (exit-hysteresis)
  occupancy thresholds **shall** satisfy `lower < upper`; violating this risks
  oscillation or permanent retry.
- **Pool sizing.** `PoolID` count and per-pool resource reservation **shall** be
  consistent across CA and HA views.
- Consistent with HAMVF's general posture, misconfiguration here is **undefined
  behavior** rather than hardware-enforced (cf. HAMVF §10.3.5 hazard list).

---

## 9. Open Issues

Tracked separately in [open-issues.md](open-issues.md). Summary:

- **OI-1** Congestion modeling: real retry rate under realistic (not worst-case)
  load; validate the 2× tax is acceptable.
- **OI-2** Grant loss / timeout reconciliation path (robustness).
- **OI-3** Fabric-internal congestion not addressed by endpoint retry.
- **OI-4** Realistic topology counter count (replace 64×64×8 worst case).
- **OI-5** Exact hysteresis thresholds & anti-oscillation proof.
- **OI-6** VC-by-VC retryability audit (which VCs can be fully retryable).
- **OI-7** Interaction with HAMVF early-completion (§8.10.23) and existing
  DRS/NDR trash-and-retry (§8.10.28.1) — unify or keep separate.

---

## 10. References

- `SCF_GEN4_R2204_HAMVF_HAS` Rev 2204 — HAMVF IP HAS
  (NIP 2.0 flow control §5.8; HNID/HTID routing §8.10.7; early completion
  §8.10.23; DRS/NDR trash-and-retry deadlock breaker §8.10.28.1;
  misconfiguration hazards §10.3.5).
- SCF IP Overall HAS — VN0 credit ring, fabric flow control.
- `SCF_GEN4_LATEST_SCA_HAS` — SCF caching-agent (CA) role.
- Intel UXI Specification Rev 1 — Home Agent protocol role.
- ARM AMBA CHI (issue E or later) — E2E flow control: RetryAck, PCrdType,
  PCrdGrant.
- IRR docs index: https://docs.intel.com/documents/arch_datacenter/IRR/index.html
