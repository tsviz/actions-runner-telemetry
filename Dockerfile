FROM ubuntu:22.04

# Install necessary packages
RUN apt-get update && \
    apt-get install -y sysstat procps curl jq python3 && \
    rm -rf /var/lib/apt/lists/*

# Copy scripts
COPY entrypoint.sh /entrypoint.sh
COPY post-entrypoint.sh /post-entrypoint.sh
COPY telemetry_collector.py /telemetry_collector.py
COPY generate_report.py /generate_report.py
RUN chmod +x /entrypoint.sh /post-entrypoint.sh /telemetry_collector.py /generate_report.py

ENTRYPOINT ["/entrypoint.sh"]
