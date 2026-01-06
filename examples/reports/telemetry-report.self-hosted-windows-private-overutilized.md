# 🖥️ Runner Telemetry Dashboard

> **🔴 Status: Needs Attention** • Duration: 10.0m • Samples: 20

---

## 📊 Quick Overview

| | Current | Peak | Average |
|:--|:-------:|:----:|:-------:|
| **CPU** 🔴 | 🔴 `██████████████████░░` 93.0% | 93.0% | 69.4% |
| **Memory** 🔴 | 🔴 `██████████████████░░` 92.0% | 92.0% | 74.6% |
| **Load** 🟢 | 0.50 | 0.50 | 0.50 |

---

## 📈 Resource Usage Over Time

| 🔵 CPU % | 🟢 Memory % |
|:--------:|:-----------:|
| Peak: 93.0% / Avg: 69.4% | Peak: 92.0% / Avg: 74.6% |

```mermaid
xychart-beta
    title "CPU & Memory Usage Over Time"
    x-axis "Time (seconds)" ["0", "30", "60", "90", "120", "150", "180", "210", "240", "270", "300", "330", "360", "390", "420", "450", "480", "510", "540", "570"]
    y-axis "Usage %" 0 --> 100
    line [70.0, 55.0, 55.0, 55.0, 70.0, 55.0, 55.0, 55.0, 70.0, 55.0, 55.0, 55.0, 70.0, 55.0, 93.0, 93.0, 93.0, 93.0, 93.0, 93.0]
    line [80.0, 60.0, 60.0, 80.0, 60.0, 60.0, 80.0, 60.0, 60.0, 80.0, 60.0, 60.0, 80.0, 60.0, 92.0, 92.0, 92.0, 92.0, 92.0, 92.0]
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
    "CPU Used" : 69.4
    "CPU Idle" : 30.6
```


</td>
<td width="50%">

**Memory Usage** - Average RAM consumption

```mermaid
pie showData title Memory Utilization
    "Used" : 74.6
    "Available" : 25.4
```


</td>
</tr>
</table>

---

## ⚡ Performance Metrics

| Metric | Status | Peak | Average |
|:-------|:------:|:----:|:-------:|
| **I/O Wait** | 🟢 | 6.0% | 3.6% |
| **CPU Steal** | 🟢 | 0.0% | 0.0% |
| **Swap Usage** | 🟢 | 0.0% | 0.0% |



## 💾 I/O Summary

| Metric | Total | Avg Rate |
|:-------|------:|---------:|
| 📥 **Disk Read** | 3.0 GB | 5.1 MB/s |
| 📤 **Disk Write** | 1.7 GB | 2.9 MB/s |
| 🌐 **Network RX** | 2.1 GB | 3.6 MB/s |
| 🌐 **Network TX** | 1.3 GB | 2.3 MB/s |



---

## 📋 Per-Step Analysis

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Max Mem |
|:-----|:--------:|:-------:|:-------:|:-------:|:-------:|
| Install Dependencies | 2.8m | 60.0% | 70.0% | 66.7% | 80.0% |
| Build Application | 2.8m | 57.5% | 70.0% | 66.7% | 80.0% |
| 🔥 Run Tests | 4.4m | 85.4% | 93.0% | 86.5% | 92.0% |


> 💡 **Insights:** Longest step: **Run Tests** (4.4m) • 
> Heaviest CPU: **Run Tests** (85.4%)


---

## 💰 Runner Utilization (Self-Hosted)

> **Key Question:** Are you getting value from your self-hosted runner?

### Utilization Score: D (93%)

🔴 Poor - Job exceeds runner capacity - consider upgrading to a larger runner

`██████████████████░░` **92.6%**

### 📊 What You're Paying For vs What You're Using

| Resource | Available | Peak Used | Avg Used |
|:---------|----------:|----------:|---------:|
| **CPU Cores** | 16 | 14.9 | 11.1 |
| **RAM** | 64.0 GB | 58.9 GB | 47.7 GB |

### 🧭 Cost Context

This job ran on a **self-hosted runner**. We don't estimate your infrastructure cost.

**Recommended equivalent GitHub-hosted option**

| Runner | Cores | RAM | Cost/min | Why |
|:--|--:|--:|--:|:--|
| `Windows 32-core Larger Runner` | 32 | 128 GB | $0.168 | Needs ≥19 vCPU and ≥74 GB RAM (peak + 25% headroom) |

**What if you used a comparable GitHub-hosted runner?**

| Metric | Value |
|:-------|------:|
| **Comparable Runner** | `Windows 16-core Larger Runner` |
| **Est. Per Run** | $0.84 (10 min) |
| **Est. Monthly** (10 runs/day) | $252.00 |

Benefits of GitHub-hosted runners:
- Ephemeral, isolated VMs for clean, deterministic builds
- OS images patched and maintained by GitHub (reduced ops burden)
- Scales on demand; no capacity planning or host maintenance
- Security-hardened images and regular updates

> Pricing: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

> Private networking: You can connect GitHub-hosted runners to resources on a private network (package registries, secret managers, on-prem services). See [Private networking for GitHub-hosted runners](https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/runners/private-networking).


### 🎯 Optimization Strategy

GitHub hosted runners are most useful when jobs finish quickly and resources match the workload:


**Priority: Upgrade to Larger Runner ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **93.0%** (avg: 69.4%)
- Memory peaked at **92.0%** (avg: 74.6%)

**Recommended Runner: Windows 16-core Larger Runner (16-core, 64GB RAM)**

**Why:** Both CPU (93%) and memory (92%) are near limits.

**Expected Performance:** ~2.0x faster


**Cost Impact (accounting for faster execution):**

> ℹ️ *This cost analysis is theoretical and compares against an equivalent GitHub-hosted runner. Your self-hosted runner has no measured per-minute cost—the figures below represent what you would pay if using GitHub-hosted infrastructure.*

- Current: $0.42/run (10 min @ $0.042/min)
- Recommended: $0.42/run (est. 5.0 min @ $0.084/min)
 - **Per-run difference: +$0.00** (+0%)

**Monthly Cost Comparison** (10 runs/day, 300 runs/month):
- Current: $126.00
- Recommended: $126.00
 - **Monthly difference: +$0.00** (+0%)

**✅ Same Cost, 2.0x Faster!** Get 2.0x faster job execution at the same price.

**Hidden Value Breakdown:**
- Developer waiting time: 25.0 hours/month = **$1875/month**
- Fewer timeouts: 30→3 per month = **$180/month savings** (Assuming 10% timeout rate at current utilization, ~5 min dev time per timeout)

**Total Hidden Value: ~$2055/month** in productivity and reliability improvements!

**Note:** Larger runners require a **GitHub Team or GitHub Enterprise Cloud** plan. Not available on free tier.

**How to Switch:**


To change runners, choose a label in the same OS family. Typical availability:
- Linux: standard (ubuntu-latest) and larger 4-core, 8-core sizes.
- Windows: standard (windows-latest) and larger 4-core, 8-core sizes.
- macOS: standard (macos-latest), larger (e.g., 12‑core), and xlarge options.

For setup instructions, see: [GitHub Actions - Manage Larger Runners](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)

For pricing details, see: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)


---

## 🖥️ Runner Information

| Component | Details |
|:----------|:--------|
| **Runner** | self-hosted-custom |
| **OS** | Windows |
| **Architecture** | X64 |
| **Total Memory** | 65,536 MB |
| **CPU Cores** | 16 |


---

## 💡 Recommendations

- ⚠️ **High CPU Usage:** Peak reached 93.0%. Consider using a larger runner or optimizing compute-heavy operations.
- ⚠️ **High Memory Usage:** Peak reached 92.0%. Watch for OOM issues or consider runners with more RAM.

---

<sub>Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)</sub>
