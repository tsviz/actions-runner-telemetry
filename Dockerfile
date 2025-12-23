FROM ubuntu:22.04

# Install necessary packages: sysstat (for iostat, mpstat), procps (for top, free), curl, jq (for scripting)
RUN apt-get update && \
    apt-get install -y sysstat procps curl jq && \
    rm -rf /var/lib/apt/lists/*

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
