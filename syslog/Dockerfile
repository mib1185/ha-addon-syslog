ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk --no-cache add py3-pip \
    && pip install --break-system-packages python-systemd

COPY bashio_info.sh /
COPY journal2syslog.py /
COPY run.sh /

CMD ["/run.sh"]