# 🖥️ Runner Telemetry Dashboard

> **🟢 Status: Healthy** • Duration: 10.0m • Samples: 20

---

## 📊 Quick Overview

| | Current | Peak | Average |
|:--|:-------:|:----:|:-------:|
| **CPU** 🟢 | 🟢 `████████░░░░░░░░░░░░` 40.0% | 40.0% | 35.0% |
| **Memory** 🟢 | 🟢 `███████████░░░░░░░░░` 55.0% | 55.0% | 53.2% |
| **Load** 🟢 | 0.50 | 0.50 | 0.50 |

---

## 📈 Resource Usage Over Time

| 🔵 CPU % | 🟢 Memory % |
|:--------:|:-----------:|
| Peak: 40.0% / Avg: 35.0% | Peak: 55.0% / Avg: 53.2% |

```mermaid
xychart-beta
    title "CPU & Memory Usage Over Time"
    x-axis "Time (seconds)" ["0", "30", "60", "90", "120", "150", "180", "210", "240", "270", "300", "330", "360", "390", "420", "450", "480", "510", "540", "570"]
    y-axis "Usage %" 0 --> 100
    line [30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0, 30.0, 40.0]
    line [50.0, 55.0, 55.0, 50.0, 55.0, 55.0, 50.0, 55.0, 55.0, 50.0, 55.0, 55.0, 50.0, 55.0, 55.0, 50.0, 55.0, 55.0, 50.0, 55.0]
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
    "CPU Used" : 35.0
    "CPU Idle" : 65.0
```


</td>
<td width="50%">

**Memory Usage** - Average RAM consumption

```mermaid
pie showData title Memory Utilization
    "Used" : 53.2
    "Available" : 46.8
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
| 📥 **Disk Read** | 5.8 GB | 10.0 MB/s |
| 📤 **Disk Write** | 4.2 GB | 7.2 MB/s |
| 🌐 **Network RX** | 0.0 B | 0.0 B/s |
| 🌐 **Network TX** | 0.0 B | 0.0 B/s |



---

## 📋 Per-Step Analysis

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Max Mem |
|:-----|:--------:|:-------:|:-------:|:-------:|:-------:|
| 🔥 Install Dependencies | 2.8m | 35.0% | 40.0% | 53.3% | 55.0% |
| Build Application | 2.8m | 35.0% | 40.0% | 53.3% | 55.0% |
| Run Tests | 4.4m | 35.0% | 40.0% | 53.1% | 55.0% |


> 💡 **Insights:** Longest step: **Run Tests** (4.4m) • 
> Heaviest CPU: **Install Dependencies** (35.0%)


---

## 💰 Runner Utilization (Self-Hosted)

> **Key Question:** Are you getting value from your self-hosted runner?

### Utilization Score: C (46%)

🟡 Fair - Good with room for improvement

`█████████░░░░░░░░░░░` **46.0%**

### 📊 What You're Paying For vs What You're Using

| Resource | Available | Peak Used | Avg Used |
|:---------|----------:|----------:|---------:|
| **CPU Cores** | 8 | 3.2 | 2.8 |
| **RAM** | 32.0 GB | 17.6 GB | 17.0 GB |

### 🧭 Cost Context

This job ran on a **self-hosted runner**. We don't estimate your infrastructure cost.

**Recommended equivalent GitHub-hosted option**

| Runner | Cores | RAM | Cost/min | Why |
|:--|--:|--:|--:|:--|
| `Linux 8-core ARM Larger Runner` | 8 | 32 GB | $0.014 | Needs ≥4 vCPU and ≥22 GB RAM (peak + 25% headroom) |

**What if you used a comparable GitHub-hosted runner?**

| Metric | Value |
|:-------|------:|
| **Comparable Runner** | `Linux 8-core Larger Runner` |
| **Est. Per Run** | $0.22 (10 min) |
| **Est. Monthly** (10 runs/day) | $66.00 |

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

Current utilization (46%) is healthy. Next steps:
- Implement parallelization for slow steps
- Review caching strategies
- Monitor if you need a larger runner as usage grows


---

## 🖥️ Runner Information

| Component | Details |
|:----------|:--------|
| **Runner** | self-hosted-custom |
| **OS** | Linux |
| **Architecture** | X64 |
| **Total Memory** | 32,768 MB |
| **CPU Cores** | 8 |


---

> ✅ **All metrics within healthy thresholds**

---

<sub>Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)</sub>
