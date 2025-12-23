# Runner Telemetry Action

Collects detailed system and environment telemetry from the GitHub Actions runner for workflow observability and diagnostics.

## What it does

- Captures OS, CPU, memory, and disk stats
- Records current runner and workflow environment variables
- Outputs telemetry in both step logs and a `runner-telemetry.txt` file for further use

## Usage

```yaml
steps:
  - uses: actions/checkout@v4
  - name: Collect runner telemetry
    uses: tsviz/actions-runner-telemetry@main
    # No inputs required
    # To upload the telemetry as a workflow artifact, add:
  - name: Upload runner telemetry
    uses: actions/upload-artifact@v4
    with:
      name: runner-telemetry
      path: runner-telemetry.txt
```

## License

MIT
