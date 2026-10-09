from __future__ import annotations

import logging
import logging.handlers
import re
import socket
import ssl
from datetime import datetime
from os import environ

from systemd import journal

SYSLOG_HOST = str(environ["SYSLOG_HOST"])
SYSLOG_PORT = int(environ["SYSLOG_PORT"])
SYSLOG_PROTO = str(environ["SYSLOG_PROTO"])
SYSLOG_SSL = True if environ["SYSLOG_SSL"] == "true" else False
SYSLOG_SSL_VERIFY = True if environ["SYSLOG_SSL_VERIFY"] == "true" else False
SYSLOG_FORMAT = str(environ.get("SYSLOG_FORMAT", "rfc3164")).lower()
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
        octet_counting: bool = False,
    ) -> None:
        self.ssl = ssl
        self.octet_counting = octet_counting
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

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a record, using octet-counting framing (RFC6587/RFC5425)
        for stream sockets if enabled
        """
        if not self.octet_counting or self.socktype != socket.SOCK_STREAM:
            return super().emit(record)
        try:
            msg = self.format(record)
            if self.ident:
                msg = self.ident + msg
            prio = "<%d>" % self.encodePriority(
                self.facility, self.mapPriority(record.levelname)
            )
            data = (prio + msg).encode("utf-8")
            if not self.socket:
                self.createSocket()
            self.socket.sendall(b"%d %b" % (len(data), data))
        except Exception:
            self.handleError(record)

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


class Rfc5424Formatter(logging.Formatter):
    """
    Format log records according to RFC5424
    <PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
    (<PRI> is prepended by the SysLogHandler)
    """

    NILVALUE = "-"
    BOM = "\ufeff"

    def __init__(self, hostname: str) -> None:
        super().__init__(
            "1 %(asctime)s %(hostname)s %(appname)s %(procid)s %(msgid)s %(sd)s %(bom)s%(message)s"
        )
        self.hostname = self._header_field(hostname, 255)

    @classmethod
    def _header_field(cls, value: str | int | None, max_len: int) -> str:
        """Header fields must be printable US-ASCII without spaces or NILVALUE."""
        if value is None:
            return cls.NILVALUE
        value = re.sub(r"[^\x21-\x7e]", "", str(value))[:max_len]
        return value or cls.NILVALUE

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """ISO 8601 timestamp with microseconds and timezone offset."""
        return (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="microseconds")
        )

    def format(self, record: logging.LogRecord) -> str:
        record.hostname = self.hostname
        record.appname = self._header_field(getattr(record, "prog", None), 48)
        record.procid = self._header_field(getattr(record, "pid", None), 128)
        record.msgid = self.NILVALUE
        record.sd = self.NILVALUE
        # UTF-8 encoded MSG must start with a BOM, pure ASCII is sent as MSG-ANY
        record.bom = "" if record.getMessage().isascii() else self.BOM
        return super().format(record)


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


def normalize_message(value: str | bytes | list | None) -> str:
    """
    Ensure the journal MESSAGE field is a str
    python-systemd returns bytes for non UTF-8 data and a list for repeated fields
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(normalize_message(item) for item in value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


# start journal reader and seek to end of journal
jr = journal.Reader(path="/var/log/journal")
jr.seek_tail()
jr.get_previous()

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
    address=(SYSLOG_HOST, SYSLOG_PORT),
    socktype=socktype,
    ssl=use_ssl,
    octet_counting=SYSLOG_FORMAT == "rfc5424",
)
if SYSLOG_FORMAT == "rfc5424":
    formatter = Rfc5424Formatter(hostname=HAOS_HOSTNAME)
    # trailing NUL byte would become part of MSG in RFC5424
    syslog_handler.append_nul = False
else:
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
        extra = {"prog": entry.get("SYSLOG_IDENTIFIER"), "pid": entry.get("_PID")}
        msg = normalize_message(entry.get("MESSAGE"))

        # remove shell colors from container messages
        if (container_name := entry.get("CONTAINER_NAME")) is not None:
            msg = re.sub(r"\x1b\[\d+m", "", msg)

        # determine syslog level
        if not container_name:
            priority = entry.get("PRIORITY", 6)
            if isinstance(priority, int) and 0 <= priority <= 7:
                log_level = LOGGING_JOURNAL_PRIORITY_TO_LEVEL_MAPPING[priority]
            else:  # invalid client-supplied PRIORITY
                log_level = LOGGING_DEFAULT_LEVEL
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
