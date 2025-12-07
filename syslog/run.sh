#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

bashio::log.info "Set configuration..."
SYSLOG_HOST=$(bashio::config 'syslog_host')
export SYSLOG_HOST
SYSLOG_PORT=$(bashio::config 'syslog_port')
export SYSLOG_PORT
SYSLOG_PROTO=$(bashio::config 'syslog_protocol')
export SYSLOG_PROTO
SYSLOG_SSL=$(bashio::config 'syslog_ssl')
export SYSLOG_SSL
SYSLOG_SSL_VERIFY=$(bashio::config 'syslog_ssl_verify')
export SYSLOG_SSL_VERIFY
SYSLOG_FORMAT=$(bashio::config 'syslog_format')
export SYSLOG_FORMAT
HAOS_HOSTNAME=$(bashio::info.hostname)
export HAOS_HOSTNAME

# Run daemon
bashio::log.info "Starting the daemon..."
python3 /journal2syslog.py
