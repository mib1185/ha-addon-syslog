ARG BUILD_FROM
FROM $BUILD_FROM

RUN apt-get update \
    && apt-get install -y python3-systemd \
    && apt-get clean autoclean \
    && apt-get autoremove -y

COPY bashio_info.sh /
COPY journal2syslog.py /
COPY run.sh /

CMD ["/run.sh"]