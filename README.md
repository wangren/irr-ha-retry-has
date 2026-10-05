# IRR HA Retry — Hardware Architecture Specification (HAS)

End-to-end **retry-based flow-control** architecture for Home Agent (HA) traffic on
Iron Rapids (IRR), proposed as an alternative/complement to credit-based
backpressure. This repository holds the architecture specification and supporting
material, structured like other chiplet HAS repos.

## Status

**v0.1 — DRAFT / for discussion.** Not an approved architecture. Authored to frame
the design space, per-agent responsibilities, and open issues ahead of modeling.

## Contents

| Path | Description |
|------|-------------|
| [docs/IRR_HA_retry.md](docs/IRR_HA_retry.md) | Main architecture specification |
| [docs/IRR_HA_retry_open-issues.md](docs/IRR_HA_retry_open-issues.md) | Tracked open questions / risks to close before signoff |

## Scope

- **What the Core (Requester/CA) must change** — speculative issue, retry-aware
  tracker retention, grant-gated reissue.
- **What the Fabric (NIP/interconnect) must do** — retryable-VC handling, message
  draining, credit/retry transport ordering.
- **What the HA (HAMVF) must do** — retry-decision logic, per-source(+VC) counters,
  credit grant (PCrdGrant-equivalent) generation, QoS/throttle, livelock exit.

## Related specifications

- `SCF_GEN4_R2204_HAMVF_HAS` (Rev 2204) — HAMVF IP HAS (HA role, NIP 2.0, HSF, flow control)
- SCF IP Overall HAS — fabric/interconnect flow control, VN0 credit ring
- `SCF_GEN4_LATEST_SCA_HAS` — SCF caching-agent (CA) role
- ARM AMBA CHI (issue E+) — E2E flow control (RetryAck / PCrdGrant) reference
- Intel UXI Specification Rev 1 — Home Agent protocol role

> Internal Intel specs above are on `docs.intel.com` and are queried via the
> co-design specs MCP tool, not plain web fetch.

## Building / rendering

Markdown only; render with any Markdown viewer or `pandoc` to PDF/HTML.

## Contributing

See draft conventions in [docs/IRR_HA_retry.md](docs/IRR_HA_retry.md) §1.
File spec issues as tracker items (not inline comments), per HAS convention.
