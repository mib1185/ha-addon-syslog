ARG BUILD_FROM=ghcr.io/home-assistant/base-debian:bookworm
FROM ${BUILD_FROM}

RUN apt-get update \
    && apt-get install -y python3-systemd \
    && apt-get clean autoclean \
    && apt-get autoremove -y

COPY bashio_info.sh /
COPY journal2syslog.py /
COPY run.sh /

LABEL \
    org.opencontainers.image.title="Syslog" \
    org.opencontainers.image.description="Send your HAOS logs to a remote syslog server" \
    org.opencontainers.image.source="https://github.com/mib1185/ha-addon-syslog" \
    org.opencontainers.image.licenses="Apache License 2.0"

CMD ["/run.sh"]
