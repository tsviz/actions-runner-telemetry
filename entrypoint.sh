#!/bin/bash
set -e

echo "::group::Runner Telemetry"

# OS and kernel info
echo "OS Information:"
uname -a

# CPU and memory usage
echo -e "\nCPU and Memory Usage (top 10 processes):"
ps aux --sort=-%mem | head -n 11

# Disk usage
echo -e "\nDisk Usage:"
df -h

# CPU stats
echo -e "\nCPU Stats:"
mpstat

# GitHub Actions Runner Context
echo -e "\nGitHub Actions Context:"
echo "Runner OS: $RUNNER_OS"
echo "Job: $GITHUB_JOB"
echo "Workflow: $GITHUB_WORKFLOW"
echo "Run ID: $GITHUB_RUN_ID"
echo "Run Number: $GITHUB_RUN_NUMBER"
echo "Repository: $GITHUB_REPOSITORY"
echo "Actor: $GITHUB_ACTOR"

echo "::endgroup::"

# Optionally, write telemetry to a file
OUT_FILE=runner-telemetry.txt
{
  echo "OS Information:"; uname -a
  echo; echo "CPU and Memory Usage (top 10 processes):"; ps aux --sort=-%mem | head -n 11
  echo; echo "Disk Usage:"; df -h
  echo; echo "CPU Stats:"; mpstat
  echo; echo "GitHub Actions Context:"
  echo "Runner OS: $RUNNER_OS"
  echo "Job: $GITHUB_JOB"
  echo "Workflow: $GITHUB_WORKFLOW"
  echo "Run ID: $GITHUB_RUN_ID"
  echo "Run Number: $GITHUB_RUN_NUMBER"
  echo "Repository: $GITHUB_REPOSITORY"
  echo "Actor: $GITHUB_ACTOR"
} > "$OUT_FILE"

echo "Telemetry written to $OUT_FILE"
