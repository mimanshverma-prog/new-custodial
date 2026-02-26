#!/bin/bash

# Check if run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

echo "========================================="
echo "  Bulk Mailer Server Setup (Postfix)     "
echo "========================================="

# 1. Install Dependencies
echo "Installing Postfix, OpenDKIM, and Certbot..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y postfix opendkim opendkim-tools mailutils python3-certbot-nginx

# 2. Configure Postfix
echo "Configuring Postfix..."

# Backup original config
cp /etc/postfix/main.cf /etc/postfix/main.cf.bak

# Set Hostname (User needs to replace this)
# postconf -e "myhostname = mail.yourdomain.com"
# postconf -e "mydomain = yourdomain.com"

# Basic Settings
postconf -e "myorigin = /etc/mailname"
postconf -e "mydestination = \$myhostname, localhost.\$mydomain, localhost"
postconf -e "relayhost ="
postconf -e "mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128"
postconf -e "mailbox_size_limit = 0"
postconf -e "recipient_delimiter = +"
postconf -e "inet_interfaces = all"
postconf -e "inet_protocols = all"

# Tuning for Bulk Sending (Performance)
# -------------------------------------
# deliver multiple messages at once to the same destination
postconf -e "default_destination_concurrency_limit = 50"
# how long a message stays in queue
postconf -e "maximal_queue_lifetime = 1d"
# delay between attempts
postconf -e "queue_run_delay = 300s"
postconf -e "minimal_backoff_time = 300s"
postconf -e "maximal_backoff_time = 4000s"

# 3. Configure DKIM (DomainKeys Identified Mail)
echo "Configuring OpenDKIM..."

mkdir -p /etc/opendkim/keys
chown -R opendkim:opendkim /etc/opendkim
chmod go-rw /etc/opendkim/keys

cat > /etc/opendkim.conf <<EOF
Syslog                  yes
SyslogSuccess           yes
LogWhy                  yes
UMask                   002
RunAsUser               opendkim
Mode                    sv
Socket                  inet:8891@localhost
PidFile                 /var/run/opendkim/opendkim.pid
OversignHeaders         From
TrustAnchorFile         /usr/share/dns/root.key
UserID                  opendkim
KeyTable                refile:/etc/opendkim/key.table
SigningTable            refile:/etc/opendkim/signing.table
ExternalIgnoreList      refile:/etc/opendkim/trusted.hosts
InternalHosts           refile:/etc/opendkim/trusted.hosts
EOF

cat > /etc/default/opendkim <<EOF
SOCKET="inet:8891@localhost"
EOF

# Link Postfix to OpenDKIM
postconf -e "milter_protocol = 2"
postconf -e "milter_default_action = accept"
postconf -e "smtpd_milters = inet:localhost:8891"
postconf -e "non_smtpd_milters = inet:localhost:8891"

echo "========================================="
echo "  SETUP COMPLETE (ALMOST)                "
echo "========================================="
echo "You must now manually generate DKIM keys for your domain."
echo "Run the following command (replace yourdomain.com):"
echo ""
echo "  opendkim-genkey -s mail -d yourdomain.com -D /etc/opendkim/keys/yourdomain.com"
echo "  chown opendkim:opendkim /etc/opendkim/keys/yourdomain.com/mail.private"
echo ""
echo "Then add the keys to key.table and signing.table."
echo "Finally, restart services:"
echo "  service postfix restart"
echo "  service opendkim restart"
echo "========================================="
