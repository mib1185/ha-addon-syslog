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

# wait for new messages in journal
while True:
    change = jr.wait(timeout=None)
    for entry in jr:
        extra = {"prog": entry.get("SYSLOG_IDENTIFIER")}
        if "CONTAINER_NAME" in entry:
            msg = re.sub(r"\x1b\[\d+m", "", entry.get("MESSAGE"))
        else:
            msg = entry.get("MESSAGE")
        logger.log(level=entry.get("PRIORITY", logging.INFO), msg=msg, extra=extra)
