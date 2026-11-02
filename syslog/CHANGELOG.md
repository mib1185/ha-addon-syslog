# Changelog

## 0.6.0

- Drop support for the deprecated `armhf`, `armv7` and `i386` architectures
- Build with Docker BuildKit and the new Home Assistant builder actions
- Publish a multi-arch image to GitHub Container Registry (`ghcr.io/mib1185/ha-addon-syslog`)

## 0.5.2

- Rename add-on to app

## 0.5.1

- Fix forwarder crash on journal messages with invalid UTF-8 or repeated fields
- Fix forwarder crash on journal entries with an invalid priority

## 0.5.0

- Add option to choose between RFC3164 (BSD) and RFC5424 syslog format

## 0.4.1

- Fix tagging of containers

## 0.4.0

- Handle unavailable syslog server

## 0.3.0

- Add tls support

## 0.2.0

- Determine correct syslog level for ha core, supervisor and haos host messages

## 0.1.0

- Use pre-built images

## 0.0.2

- Make messages RFC3164 (bsd) compliant

## 0.0.1

- Initial version
