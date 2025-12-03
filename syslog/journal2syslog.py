from __future__ import annotations

import datetime
import logging
import logging.handlers
import re
import socket
import ssl
from os import environ

from systemd import journal

SYSLOG_HOST = str(environ["SYSLOG_HOST"])
SYSLOG_PORT = int(environ["SYSLOG_PORT"])
SYSLOG_PROTO = str(environ["SYSLOG_PROTO"])
SYSLOG_SSL = True if environ["SYSLOG_SSL"] == "true" else False
SYSLOG_SSL_VERIFY = True if environ["SYSLOG_SSL_VERIFY"] == "true" else False
SYSLOG_FORMAT = environ.get("SYSLOG_FORMAT", "RFC3164")
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


class TlsSysLogHandler(logging.handlers.SysLogHandler):
    def __init__(
        self,
        address: tuple[str, int]
        | str = ("localhost", logging.handlers.SYSLOG_UDP_PORT),
        facility: str | int = logging.handlers.SysLogHandler.LOG_USER,
        socktype: logging.handlers.SocketKind | None = None,
        ssl: bool | ssl.SSLContext = False,
    ) -> None:
        self.ssl = ssl
        if ssl and socktype != socket.SOCK_STREAM:
            raise RuntimeError("TLS is only support for TCP connections")
        super().__init__(address, facility, socktype)

    def _wrap_sock_ssl(self, sock: socket.socket, host: str):
        """Wrap a tcp socket into a ssl context."""
        if isinstance(self.ssl, ssl.SSLContext):
            context = self.ssl
        else:
            context = ssl.create_default_context()

        return context.wrap_socket(sock, server_hostname=host)

    def handleError(self, _):
        """
        Handle errors silent
        Close failing socket so next emit will try to create a new socket
        """
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def createSocket(self):
        """
        Try to create a socket and, if it's not a datagram socket, connect it
        to the other end. This method is called during handler initialization,
        but it's not regarded as an error if the other end isn't listening yet
        --- the method will be called again when emitting an event,
        if there is no socket at that point.
        """
        address = self.address
        socktype = self.socktype

        if isinstance(address, str):
            self.unixsocket = True
            # Syslog server may be unavailable during handler initialisation.
            # C's openlog() function also ignores connection errors.
            # Moreover, we ignore these errors while logging, so it's not worse
            # to ignore it also here.
            try:
                self._connect_unixsocket(address)
            except OSError:
                pass
        else:
            self.unixsocket = False
            if socktype is None:
                socktype = socket.SOCK_DGRAM
            host, port = address
            ress = socket.getaddrinfo(host, port, 0, socktype)
            if not ress:
                raise OSError("getaddrinfo returns an empty list")
            for res in ress:
                af, socktype, proto, _, sa = res
                err = sock = None
                try:
                    sock = socket.socket(af, socktype, proto)
                    if self.ssl:
                        sock = self._wrap_sock_ssl(sock, host)
                    if socktype == socket.SOCK_STREAM:
                        sock.connect(sa)
                    break
                except (OSError, ssl.SSLError) as exc:
                    err = exc
                    if sock is not None:
                        sock.close()
            if isinstance(err, ssl.SSLError):
                # only fail on ssl errors
                raise err
            self.socket = sock
            self.socktype = socktype


class RFC5424Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        """Return the creation time of the specified LogRecord as formatted text."""
        dt = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc)
        return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


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

use_ssl = SYSLOG_SSL
if SYSLOG_SSL and not SYSLOG_SSL_VERIFY:
    use_ssl = ssl.create_default_context()
    use_ssl.check_hostname = False
    use_ssl.verify_mode = ssl.CERT_NONE

syslog_handler = TlsSysLogHandler(
    address=(SYSLOG_HOST, SYSLOG_PORT), socktype=socktype, ssl=use_ssl
)

if SYSLOG_FORMAT == "RFC5424":
    formatter = RFC5424Formatter(
        fmt="1 %(asctime)s %(ip)s %(prog)s %(procid)s - - %(message)s",
        defaults={"ip": HAOS_HOSTNAME},
    )
else:
    formatter = logging.Formatter(
        fmt="%(asctime)s %(ip)s %(prog)s: %(message)s",
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
        if SYSLOG_FORMAT == "RFC5424":
            # RFC 5424 parameters
            prog = entry.get("SYSLOG_IDENTIFIER") or "-"
            procid = entry.get("_PID") or "-"
            extra = {"prog": prog, "procid": procid}
        else:
            extra = {"prog": entry.get("SYSLOG_IDENTIFIER")}

        # remove shell colors from container messages
        if (container_name := entry.get("CONTAINER_NAME")) is not None:
            msg = re.sub(r"\x1b\[[0-9;]*m", "", entry.get("MESSAGE"))
        else:
            msg = entry.get("MESSAGE")

        if SYSLOG_FORMAT == "RFC5424" and isinstance(msg, str):
            msg = msg.replace("\n", "#012").replace("\r", "")

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
