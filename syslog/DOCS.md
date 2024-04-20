# Syslog Home Assistant add-on

## How to use

This add-on allows you to send your HAOS logs to a remote syslog server.

## Configuration

Add-on configuration:

```yaml
syslog_host: syslog.local
syslog_port: 514
syslog_protocol: udp
```

| key | name | description |
| --- | ---- | ----------- |
| `syslog_host` | Syslog host | The hostname or IP address of the remote syslog server to send HAOS logs to. |
| `syslog_port` | Syslog port | The port of the remote syslog server to send HAOS logs to. |
| `syslog_protocol` | Transfer protocol | The protocol to be used to send HAOS logs. |

## Support

In case you've found a bug, please [open an issue on our GitHub][issue].

[issue]: https://github.com/mib1185/ha-addon-syslog/issues
