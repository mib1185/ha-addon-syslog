#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

bashio::log.info "Set configuration..."
SYSLOG_HOST=$(bashio::config 'syslog_host')
export SYSLOG_HOST
SYSLOG_PORT=$(bashio::config 'syslog_port')
export SYSLOG_PORT
SYSLOG_PROTO=$(bashio::config 'syslog_protocol')
export SYSLOG_PROTO

# Run daemon
bashio::log.info "Starting the daemon..."
python3 /journal2syslog.py
