# Syslog Home Assistant add-on

## How to use

This add-on allows you to send your HAOS logs to a remote syslog server.

## Configuration

Add-on configuration:

```yaml
syslog_host: syslog.local
syslog_port: 514
syslog_protocol: udp
syslog_ssl: false
syslog_ssl_verfify: false
syslog_use_iso8601: false
```

| key | name | description |
| --- | ---- | ----------- |
| `syslog_host` | Syslog host | The hostname or IP address of the remote syslog server to send HAOS logs to. |
| `syslog_port` | Syslog port | The port of the remote syslog server to send HAOS logs to. |
| `syslog_protocol` | Transfer protocol | The protocol to be used to send HAOS logs. |
| `syslog_ssl` | SSL encryption | Whether or not to to use ssl encryption (only supported with tcp). |
| `syslog_ssl_verfify` | SSL verify | Whether or not to verify ssl certificate. |
| `syslog_use_iso8601` | Use ISO8601 Timestamps |  Whether or not to use ISO8601-formatted timestamps. |

## Support

In case you've found a bug, please [open an issue on GitHub][issue].

[issue]: https://github.com/mib1185/ha-addon-syslog/issues
