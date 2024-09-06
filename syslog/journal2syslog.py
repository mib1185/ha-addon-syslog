from __future__ import annotations

import logging
import logging.handlers
from os import environ
import re
import socket
from systemd import journal

SYSLOG_HOST = str(environ["SYSLOG_HOST"])
SYSLOG_PORT = int(environ["SYSLOG_PORT"])
SYSLOG_PROTO = str(environ["SYSLOG_PROTO"])
HAOS_HOSTNAME = str(environ["HAOS_HOSTNAME"])

LOGGING_NAME_TO_LEVEL_MAPPING = logging.getLevelNamesMapping()
LOGGING_JOURNAL_PRIORITY_TO_LEVEL_MAPPING = [
    logging.CRITICAL,  # 0 - emerg
    logging.CRITICAL,  # 1 - alert
    logging.CRITICAL,  # 2 - crit
    logging.ERROR,  # 3 - err
    logging.WARNING,  # 4 - warning
    logging.INFO,  # 5 - notice
    logging.INFO,  # 6 - info
    logging.DEBUG,  # 7 - debug
]
LOGGING_DEFAULT_LEVEL = logging.INFO
PATTERN_LOGLEVEL_HA = re.compile(
    r"^\S+ \S+ (?P<level>INFO|WARNING|DEBUG|ERROR|CRITICAL) "
)
CONTAINER_PATTERN_MAPPING = {
    "homeassistant": PATTERN_LOGLEVEL_HA,
    "hassio_supervisor": PATTERN_LOGLEVEL_HA,
}


def parse_log_level(message: str, container_name: str) -> int:
    """
    Try to determine logging level from message
    return: logging.<LEVELNAME> if determined
    return: logging.NOTSET if not determined
    """
    if pattern := CONTAINER_PATTERN_MAPPING.get(container_name):
        if (match := pattern.search(message)) is None:
            return logging.NOTSET
        return LOGGING_NAME_TO_LEVEL_MAPPING.get(
            match.group("level").upper(), logging.NOTSET
        )
    return logging.NOTSET


# start journal reader and seek to end of journal
jr = journal.Reader(path="/var/log/journal")
jr.this_boot()
jr.seek_tail()
jr.get_previous()
jr.get_next()

# start logger
logger = logging.getLogger("")
logger.setLevel(logging.NOTSET)

if SYSLOG_PROTO.lower() == "udp":
    socktype = socket.SOCK_DGRAM
else:
    socktype = socket.SOCK_STREAM

syslog_handler = logging.handlers.SysLogHandler(
    address=(SYSLOG_HOST, SYSLOG_PORT), socktype=socktype
)
formatter = logging.Formatter(
    f"%(asctime)s %(ip)s %(prog)s: %(message)s",
    defaults={"ip": HAOS_HOSTNAME},
    datefmt="%b %d %H:%M:%S",
)
syslog_handler.setFormatter(formatter)
logger.addHandler(syslog_handler)

last_container_log_level: dict[str, int] = {}

# wait for new messages in journal
while True:
    change = jr.wait(timeout=None)
    for entry in jr:
        extra = {"prog": entry.get("SYSLOG_IDENTIFIER")}

        # remove shell colors from container messages
        if (container_name := entry.get("CONTAINER_NAME")) is not None:
            msg = re.sub(r"\x1b\[\d+m", "", entry.get("MESSAGE"))
        else:
            msg = entry.get("MESSAGE")

        # determine syslog level
        if not container_name:
            log_level = LOGGING_JOURNAL_PRIORITY_TO_LEVEL_MAPPING[
                entry.get("PRIORITY", 6)
            ]
        elif container_name not in CONTAINER_PATTERN_MAPPING:
            log_level = LOGGING_DEFAULT_LEVEL
        elif log_level := parse_log_level(msg, container_name):
            last_container_log_level[container_name] = log_level
        else:  # use last log level if it could not be parsed (eq. for tracebacks)
            log_level = last_container_log_level.get(
                container_name, LOGGING_DEFAULT_LEVEL
            )

        # send syslog message
        logger.log(level=log_level, msg=msg, extra=extra)
