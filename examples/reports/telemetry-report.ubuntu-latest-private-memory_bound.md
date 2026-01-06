# 🖥️ Runner Telemetry Dashboard

> **🔴 Status: Needs Attention** • Duration: 5.0m • Samples: 20

---

## 📊 Quick Overview

| | Current | Peak | Average |
|:--|:-------:|:----:|:-------:|
| **CPU** 🟢 | 🟢 `███████░░░░░░░░░░░░░` 35.0% | 45.0% | 37.5% |
| **Memory** 🔴 | 🔴 `█████████████████░░░` 85.0% | 92.0% | 87.5% |
| **Load** 🟢 | 0.50 | 0.50 | 0.50 |

---

## 📈 Resource Usage Over Time

| 🔵 CPU % | 🟢 Memory % |
|:--------:|:-----------:|
| Peak: 45.0% / Avg: 37.5% | Peak: 92.0% / Avg: 87.5% |

```mermaid
xychart-beta
    title "CPU & Memory Usage Over Time"
    x-axis "Time (seconds)" ["0", "15", "30", "45", "60", "75", "90", "105", "120", "135", "150", "165", "180", "195", "210", "225", "240", "255", "270", "285"]
    y-axis "Usage %" 0 --> 100
    line [45.0, 35.0, 35.0, 35.0, 45.0, 35.0, 35.0, 35.0, 45.0, 35.0, 35.0, 35.0, 45.0, 35.0, 35.0, 35.0, 45.0, 35.0, 35.0, 35.0]
    line [92.0, 85.0, 85.0, 92.0, 85.0, 85.0, 92.0, 85.0, 85.0, 92.0, 85.0, 85.0, 92.0, 85.0, 85.0, 92.0, 85.0, 85.0, 92.0, 85.0]
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
    "CPU Used" : 37.5
    "CPU Idle" : 62.5
```


</td>
<td width="50%">

**Memory Usage** - Average RAM consumption

```mermaid
pie showData title Memory Utilization
    "Used" : 87.5
    "Available" : 12.5
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
| 📥 **Disk Read** | 300.0 MB | 1.0 MB/s |
| 📤 **Disk Write** | 210.0 MB | 716.8 KB/s |
| 🌐 **Network RX** | 240.0 MB | 819.2 KB/s |
| 🌐 **Network TX** | 150.0 MB | 512.0 KB/s |

> ℹ️ Estimated baseline shown (no I/O telemetry captured).


---

## 📋 Per-Step Analysis

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Max Mem |
|:-----|:--------:|:-------:|:-------:|:-------:|:-------:|
| 🔥 Install Dependencies | 1.4m | 38.3% | 45.0% | 87.3% | 92.0% |
| Build Application | 1.4m | 36.7% | 45.0% | 87.3% | 92.0% |
| Run Tests | 2.2m | 37.5% | 45.0% | 87.6% | 92.0% |


> 💡 **Insights:** Longest step: **Run Tests** (2.2m) • 
> Heaviest CPU: **Install Dependencies** (38.3%)


---

## 💰 Runner Utilization & Cost Efficiency

> **Key Question:** Are you getting maximum value from your GitHub hosted runner?

### Utilization Score: C (64%)

🟡 Fair - Job is straining resources - consider upgrading to a larger runner

`████████████░░░░░░░░` **63.8%**

### 📊 What You're Paying For vs What You're Using

| Resource | Available | Peak Used | Avg Used |
|:---------|----------:|----------:|---------:|
| **CPU Cores** | 2 | 0.9 | 0.8 |
| **RAM** | 7.0 GB | 6.4 GB | 6.1 GB |

### 💵 Cost Analysis (Jan 2026+ Pricing)

> 📖 Pricing reference: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

| Metric | Value |
|:-------|------:|
| **Runner Type** | `Ubuntu Standard Runner` |
| **This Run** | $0.03 (5 min) |
| **Est. Monthly** (10 runs/day) | $9.00 |


### 🎯 Optimization Strategy

GitHub hosted runners are most useful when jobs finish quickly and resources match the workload:


**Priority: Upgrade to Larger Runner ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **45.0%** (avg: 37.5%)
- Memory peaked at **92.0%** (avg: 87.5%)

**Recommended Runner: Linux 4-core Larger Runner (4-core, 16GB RAM)**

**Why:** Memory maxed out at 92%.

**Expected Performance:** ~2.0x faster (upgrade from 2 to 4 cores)


**Cost Impact (accounting for faster execution):**
- Current: $0.03/run (5 min @ $0.006/min)
- Recommended: $0.03/run (est. 2.5 min @ $0.012/min)
 - **Per-run difference: +$0.00** (+0%)

**Monthly Cost Comparison** (10 runs/day, 300 runs/month):
- Current: $9.00
- Recommended: $9.00
 - **Monthly difference: +$0.00** (+0%)

**✅ Same Cost, 2.0x Faster!** Get 2.0x faster job execution at the same price.

**Hidden Value Breakdown:**
- Developer waiting time: 12.5 hours/month = **$938/month**
- Fewer timeouts: 30→3 per month = **$170/month savings** (Assuming 10% timeout rate at current utilization, ~5 min dev time per timeout)

**Total Hidden Value: ~$1107/month** in productivity and reliability improvements!

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
| **Runner** | ubuntu-latest |
| **OS** | Linux |
| **Architecture** | X64 |
| **Total Memory** | 7,168 MB |
| **CPU Cores** | 2 |


---

## 💡 Recommendations

- ⚠️ **High Memory Usage:** Peak reached 92.0%. Watch for OOM issues or consider runners with more RAM.

---

<sub>Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)</sub>
