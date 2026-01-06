# 🖥️ Runner Telemetry Dashboard

> **🟢 Status: Healthy** • Duration: 10.0m • Samples: 20

---

## 📊 Quick Overview

| | Current | Peak | Average |
|:--|:-------:|:----:|:-------:|
| **CPU** 🟢 | 🟢 `███████░░░░░░░░░░░░░` 35.0% | 45.0% | 38.5% |
| **Memory** 🟢 | 🟢 `█████████░░░░░░░░░░░` 45.0% | 50.0% | 46.2% |
| **Load** 🟢 | 0.50 | 0.50 | 0.50 |

---

## 📈 Resource Usage Over Time

| 🔵 CPU % | 🟢 Memory % |
|:--------:|:-----------:|
| Peak: 45.0% / Avg: 38.5% | Peak: 50.0% / Avg: 46.2% |

```mermaid
xychart-beta
    title "CPU & Memory Usage Over Time"
    x-axis "Time (seconds)" ["0", "30", "60", "90", "120", "150", "180", "210", "240", "270", "300", "330", "360", "390", "420", "450", "480", "510", "540", "570"]
    y-axis "Usage %" 0 --> 100
    line [45.0, 35.0, 35.0, 45.0, 35.0, 35.0, 45.0, 35.0, 35.0, 45.0, 35.0, 35.0, 45.0, 35.0, 35.0, 45.0, 35.0, 35.0, 45.0, 35.0]
    line [50.0, 45.0, 45.0, 45.0, 50.0, 45.0, 45.0, 45.0, 50.0, 45.0, 45.0, 45.0, 50.0, 45.0, 45.0, 45.0, 50.0, 45.0, 45.0, 45.0]
```



---

## 🔄 Average Resource Utilization

This shows the average CPU and memory usage during your job:

<table>
<tr>
<td width="50%">

**CPU Usage** - Average across all cores

```mermaid
pie showData title Resource Utilization
    "CPU Used" : 38.5
    "CPU Idle" : 61.5
```


</td>
<td width="50%">

**Memory Usage** - Average RAM consumption

```mermaid
pie showData title Memory Utilization
    "Used" : 46.2
    "Available" : 53.8
```


</td>
</tr>
</table>

---

## ⚡ Performance Metrics

| Metric | Status | Peak | Average |
|:-------|:------:|:----:|:-------:|
| **I/O Wait** | 🟢 | 0.6% | 0.6% |
| **CPU Steal** | 🟢 | 0.2% | 0.2% |
| **Swap Usage** | 🟢 | 0.8% | 0.8% |

> ℹ️ Estimated baseline shown (no telemetry for I/O/CPU wait).


## 💾 I/O Summary

| Metric | Total | Avg Rate |
|:-------|------:|---------:|
| 📥 **Disk Read** | 0.0 B | 0.0 B/s |
| 📤 **Disk Write** | 0.0 B | 0.0 B/s |
| 🌐 **Network RX** | 4.2 GB | 7.2 MB/s |
| 🌐 **Network TX** | 2.2 GB | 3.8 MB/s |



---

## 📋 Per-Step Analysis

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Max Mem |
|:-----|:--------:|:-------:|:-------:|:-------:|:-------:|
| Install Dependencies | 2.8m | 38.3% | 45.0% | 46.7% | 50.0% |
| Build Application | 2.8m | 38.3% | 45.0% | 45.8% | 50.0% |
| 🔥 Run Tests | 4.4m | 38.8% | 45.0% | 46.2% | 50.0% |


> 💡 **Insights:** Longest step: **Run Tests** (4.4m) • 
> Heaviest CPU: **Run Tests** (38.8%)


---

## 💰 Runner Utilization (Self-Hosted)

> **Key Question:** Are you getting value from your self-hosted runner?

### Utilization Score: C (47%)

🟡 Fair - Good with room for improvement

`█████████░░░░░░░░░░░` **47.0%**

### 📊 What You're Paying For vs What You're Using

| Resource | Available | Peak Used | Avg Used |
|:---------|----------:|----------:|---------:|
| **CPU Cores** | 12 | 5.4 | 4.6 |
| **RAM** | 48.0 GB | 24.0 GB | 22.2 GB |

### 🧭 Cost Context

This job ran on a **self-hosted runner**. We don't estimate your infrastructure cost.

**Recommended equivalent GitHub-hosted option**

| Runner | Cores | RAM | Cost/min | Why |
|:--|--:|--:|--:|:--|
| `macOS 13 Large Runner (Intel)` | 12 | 30 GB | $0.077 | Needs ≥7 vCPU and ≥30 GB RAM (peak + 25% headroom) |

**What if you used a comparable GitHub-hosted runner?**

| Metric | Value |
|:-------|------:|
| **Comparable Runner** | `macOS 13 Large Runner (Intel)` |
| **Est. Per Run** | $0.77 (10 min) |
| **Est. Monthly** (10 runs/day) | $231.00 |

Benefits of GitHub-hosted runners:
- Ephemeral, isolated VMs for clean, deterministic builds
- OS images patched and maintained by GitHub (reduced ops burden)
- Scales on demand; no capacity planning or host maintenance
- Security-hardened images and regular updates

> Pricing: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

> Private networking: You can connect GitHub-hosted runners to resources on a private network (package registries, secret managers, on-prem services). See [Private networking for GitHub-hosted runners](https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/runners/private-networking).


### 🎯 Optimization Strategy

GitHub hosted runners are most useful when jobs finish quickly and resources match the workload:


**Status: Good with Room for Improvement**

Current utilization (47%) is healthy. Next steps:
- Implement parallelization for slow steps
- Review caching strategies
- Monitor if you need a larger runner as usage grows


---

## 🖥️ Runner Information

| Component | Details |
|:----------|:--------|
| **Runner** | self-hosted-custom |
| **OS** | MacOS |
| **Architecture** | X64 |
| **Total Memory** | 49,152 MB |
| **CPU Cores** | 12 |


---

> ✅ **All metrics within healthy thresholds**

---

<sub>Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)</sub>
