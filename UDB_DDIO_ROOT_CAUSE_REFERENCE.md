# UDB / DDIO Coherency Bottleneck Reference

## HSD reference

- HSD article: https://hsdes.intel.com/appstore/article-one/#/14027859082
- Title: [DMR A0][PCIe][VPP] VPP IPSec workload is 40%-55% short of target on X4

## Executive summary

Root cause is a SoC performance-architecture bottleneck in the IO/coherency path, initially exposed by a DDIO workload but not limited to DDIO traffic. On DMR, IO transactions that require coherency handling through HAMVF must obtain and hold a UDB entry until the snoop response returns. As a result, when one agent becomes bottlenecked on accesses that hit in a core’s L2 cache (for example, around 30 GB/s), other agents issuing unrelated coherent traffic can be constrained by the same shared limitation. This is not addressed by simply adding more UDB entries; the lack of a sufficient QoS/fairness mechanism exacerbates multi-agent contention.

## Detailed root cause

- IO reads and writes that hit in a core’s L2 cache are limited to roughly 30 GB/s.
- This L2-servicing bandwidth limit itself is understood and appears consistent with prior generations.
- On DMR, coherent IO transactions through HAMVF require a UDB entry that remains allocated until the snoop response returns.
- The issue is not limited to DDIO write-update traffic into CBB caches. It can also occur when DDIO write push/update to CBB caches is not used, including modes such as IOLLC allocation mode or persistent memory mode.
- Synthetic results indicate that the same glass jaw can be triggered by IO read traffic alone: if one agent continuously reads data that is being sourced from a core’s L2 (for example, because the core recently modified it), that traffic can degrade other unrelated IO reads, even when those other reads are targeting memory.
- The contention therefore extends beyond classic DDIO benchmarks. VPP IPSec was the workload that exposed the issue, but the underlying bottleneck is a broader shared coherency/UDB resource limitation.
- There is also suspicion that similar degradation may arise from core-only traffic patterns, for example if some cores on one CBB continuously hit in an L2 on another CBB, although this requires further confirmation.
- The issue is therefore not simply a matter of adding more UDB entries; the root concern is the lack of a sufficient QoS/fairness mechanism for shared coherent traffic across agents.

## Engineering interpretation

The likely interpretation is that this is an internal implementation-side tracking structure in the coherent IO path, not a public specification-level architectural object. The public architecture still describes the higher-level CA/HA split and target-side occupancy/admission behavior, but the issue itself manifests as shared outstanding-request tracking and fairness contention deeper in the SoC path.

## Related issue wording

> [SOC] Perf Arch bottleneck. When one IO device is bottlenecked on DDIO BW (30GB/s for L2 hits) all IO devices issuing DDIO will be limited to that same BW due to the implementation that all DDIO Reads and Writes must obtain and hold a UDB entry. This is not simply more UDB entries makes go faster, but the lack of a QoS mechanism impacts multi-device fairness.

## Debug progress timeline

Debug progressed efficiently from a root-cause timeline perspective, with the issue identified in approximately four days. The team narrowed the root cause to a SoC performance-architecture bottleneck in the IO/coherency path affecting DDIO traffic through HAMVF/UDB.

EMON was instrumental in isolating the bottleneck. The debug and telemetry items that significantly improved time-to-root-cause included:

- per-device DDIO bandwidth counters and metrics
- L2-hit versus L3-hit DDIO visibility
- HAMVF/UDB occupancy and stall counters
- per-CBB and xbar contention counters
- DDIO QoS and fairness telemetry

## Recommendation

Based on the team discussions, this issue should have been caught in emulation but escaped to post-silicon due to insufficient coverage. The recommendation is to develop a performance simulator that can be used early in the architecture definition phase to accurately model coherent multi-agent workloads and catch issues like this before silicon.

## HSD note from clone / triage context

- CloneScript reference: [spec cloned to server.bugeco.id=22022505612] of component=soc.top in release=dmrhub-a0
- fix_id: 14028321208
- fix_ip: bios
- No hardware fix on DMR. Hardware fix needed for COR/NWP.
- BIOS knob already implemented that helps mitigate the performance loss: https://hsdes.intel.com/appstore/article-one/#/article/14028266644
- BIOS knob is not a fix; it is a partial mitigation only and may not improve performance in all situations.
- If any other mitigations are found, they will be filed separately.

## Conclusion

This issue is best understood as a shared coherent-traffic bottleneck in the SoC IO path, where a single agent’s L2-hit-induced stall can suppress unrelated coherent traffic because all such transactions must contend for the same UDB-backed tracking resource. The constructive fix is not simply more entries; the required solution is a better QoS/fairness mechanism and earlier architecture-level performance modeling to catch similar problems before silicon.
