#!/bin/bash

# Initialize
cd /opt/glassfish
./reset

# Copy over the new configuration

rm -f /opt/glassfish/current/glassfish/domains/domain1/config/domain.xml
cp /tmp/relay/glassfish_configure/domain.xml /opt/glassfish/current/glassfish/domains/domain1/config

