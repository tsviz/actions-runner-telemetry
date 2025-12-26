#!/bin/bash
# Post-entrypoint: Runs automatically at end of job to stop collection and generate report
# Note: GitHub Actions runs this immediately after the action step completes, not after all steps.
# We don't do anything here - let explicit stop steps handle report generation.

# Configuration
ENABLED="${INPUT_ENABLED:-true}"

# Check if action is disabled
if [ "$ENABLED" = "false" ] || [ "$ENABLED" = "0" ] || [ "$ENABLED" = "no" ]; then
  exit 0
fi

# Silently exit - don't interfere with running collections
# The explicit 'mode: stop' step in the workflow will handle report generation
exit 0
