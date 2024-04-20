import logging
import logging.handlers
from os import environ
import socket
from systemd import journal

SYSLOG_HOST = str(environ["SYSLOG_HOST"])
SYSLOG_PORT = int(environ["SYSLOG_PORT"])
SYSLOG_PROTO = str(environ["SYSLOG_PROTO"])

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
    socktype=socket.SOCK_DGRAM
else:
    socktype=socket.SOCK_STREAM
logger.addHandler(logging.handlers.SysLogHandler(address=(SYSLOG_HOST, SYSLOG_PORT), socktype=socktype))

# wait for new messages in journal
while True:
    change = jr.wait(timeout=None)
    for entry in jr:
        if "CONTAINER_NAME" in entry:
            msg = f"{entry.get('__REALTIME_TIMESTAMP')} | {entry.get('SYSLOG_IDENTIFIER')} | {entry.get('MESSAGE')}"
        else:
            msg = f"{entry.get('__REALTIME_TIMESTAMP')} | host | {entry.get('SYSLOG_IDENTIFIER')} : {entry.get('MESSAGE')}"
        logger.log(level=entry.get('PRIORITY', logging.INFO), msg=msg)
