ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk --no-cache add py3-pip pkgconfig elogind-dev gcc python3-dev libc-dev \
    && pip install --break-system-packages systemd-python

COPY bashio_info.sh /
COPY journal2syslog.py /
COPY run.sh /

CMD ["/run.sh"]