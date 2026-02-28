#!/bin/bash

# ==============================================================================
# 🚀 Zateway Bulk Mailer - Enterprise Authentication Setup (SPF/DKIM/DMARC/TLS)
# ==============================================================================

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (sudo bash setup_server.sh)"
  exit 1
fi

echo "========================================="
echo "  Enterprise Mail Server Setup (Postfix) "
echo "========================================="

# 1. Ask for Domain Name
read -p "Enter your main sending domain (e.g., zateway.com): " MAIN_DOMAIN
if [ -z "$MAIN_DOMAIN" ]; then
    echo "❌ Domain cannot be empty. Exiting."
    exit 1
fi

HOSTNAME="mail.$MAIN_DOMAIN"
echo "✅ Configuring server for: $HOSTNAME"

# 2. Get Public IP
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com)
echo "✅ Server IP detected: $PUBLIC_IP"

# 3. Install Dependencies
echo "⏳ Installing Postfix, OpenDKIM, and Security Tools..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y postfix opendkim opendkim-tools mailutils curl iptables dnsutils > /dev/null 2>&1

# 4. Configure Postfix (High Volume & TLS)
echo "⏳ Tuning Postfix for 1M/day & Opportunistic TLS..."

cp /etc/postfix/main.cf /etc/postfix/main.cf.bak

# Base Config
postconf -e "myhostname = $HOSTNAME"
postconf -e "mydomain = $MAIN_DOMAIN"
postconf -e "myorigin = /etc/mailname"
echo "$MAIN_DOMAIN" > /etc/mailname
postconf -e "mydestination = \$myhostname, localhost.\$mydomain, localhost, \$mydomain"
postconf -e "relayhost ="
postconf -e "mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128 172.16.0.0/12 192.168.0.0/16 10.0.0.0/8"

# Performance Tuning for Bulk (1M/day)
postconf -e "default_destination_concurrency_limit = 50"
postconf -e "maximal_queue_lifetime = 1d"
postconf -e "bounce_queue_lifetime = 1d"
postconf -e "queue_run_delay = 300s"
postconf -e "minimal_backoff_time = 300s"
postconf -e "maximal_backoff_time = 4000s"

# Security: Enable Opportunistic TLS (Removes Red Padlock in Gmail)
postconf -e "smtp_tls_security_level = may"
postconf -e "smtp_tls_loglevel = 1"
postconf -e "smtpd_tls_security_level = may"
postconf -e "smtpd_tls_loglevel = 1"

# 5. Fully Automate DKIM (The "Digital Signature")
echo "⏳ Generating 2048-bit RSA DKIM Keys (Industry Standard)..."

mkdir -p /etc/opendkim/keys/$MAIN_DOMAIN
chown -R opendkim:opendkim /etc/opendkim

# Generate the Key
opendkim-genkey -b 2048 -s mail -d $MAIN_DOMAIN -D /etc/opendkim/keys/$MAIN_DOMAIN
chown opendkim:opendkim /etc/opendkim/keys/$MAIN_DOMAIN/mail.private
chmod 600 /etc/opendkim/keys/$MAIN_DOMAIN/mail.private

# Configure OpenDKIM Files
echo "mail._domainkey.$MAIN_DOMAIN $MAIN_DOMAIN:mail:/etc/opendkim/keys/$MAIN_DOMAIN/mail.private" > /etc/opendkim/KeyTable
echo "*@$MAIN_DOMAIN mail._domainkey.$MAIN_DOMAIN" > /etc/opendkim/SigningTable
echo "127.0.0.1" > /etc/opendkim/TrustedHosts
echo "localhost" >> /etc/opendkim/TrustedHosts
echo "$HOSTNAME" >> /etc/opendkim/TrustedHosts
echo "$MAIN_DOMAIN" >> /etc/opendkim/TrustedHosts

# Main OpenDKIM Config
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
KeyTable                refile:/etc/opendkim/KeyTable
SigningTable            refile:/etc/opendkim/SigningTable
ExternalIgnoreList      refile:/etc/opendkim/TrustedHosts
InternalHosts           refile:/etc/opendkim/TrustedHosts
EOF

# Link Postfix to DKIM
postconf -e "milter_protocol = 2"
postconf -e "milter_default_action = accept"
postconf -e "smtpd_milters = inet:localhost:8891"
postconf -e "non_smtpd_milters = inet:localhost:8891"

# Restart Services
systemctl restart opendkim
systemctl restart postfix
systemctl enable opendkim
systemctl enable postfix

# Extract DKIM Public Key for the user
DKIM_RECORD=$(cat /etc/opendkim/keys/$MAIN_DOMAIN/mail.txt | grep -v "^-" | tr -d '\n\t\r "' | sed 's/mail._domainkeyIN//g')

echo ""
echo "========================================================================="
echo " 🎉 SERVER SETUP COMPLETE! NOW CONFIGURE YOUR DNS (GoDaddy/Cloudflare) 🎉"
echo "========================================================================="
echo "CRITICAL: Emails will go to SPAM until you add these EXACT records to your domain."
echo ""

echo "1️⃣ A Record (Points domain to server)"
echo "   Type: A"
echo "   Name: mail"
echo "   Value: $PUBLIC_IP"
echo "---------------------------------------------------"

echo "2️⃣ MX Record (Tells internet where to send replies)"
echo "   Type: MX"
echo "   Name: @"
echo "   Value: $HOSTNAME"
echo "   Priority: 10"
echo "---------------------------------------------------"

echo "3️⃣ SPF Record (Prevents Spoofing)"
echo "   Type: TXT"
echo "   Name: @"
echo "   Value: v=spf1 mx a ip4:$PUBLIC_IP ~all"
echo "---------------------------------------------------"

echo "4️⃣ DKIM Record (The Digital Signature - COPY CAREFULLY)"
echo "   Type: TXT"
echo "   Name: mail._domainkey"
echo "   Value: $DKIM_RECORD"
echo "---------------------------------------------------"

echo "5️⃣ DMARC Record (Strict Enforcement)"
echo "   Type: TXT"
echo "   Name: _dmarc"
echo "   Value: v=DMARC1; p=quarantine; rua=mailto:admin@$MAIN_DOMAIN;"
echo "---------------------------------------------------"
echo "6️⃣ rDNS (Reverse DNS)"
echo "   Go to your VPS Provider Dashboard (e.g., Contabo/Hetzner)"
echo "   Set the Reverse DNS for IP $PUBLIC_IP to: $HOSTNAME"
echo "========================================================================="
echo "Done! Run 'python3 check_dns.py' after 15 mins to verify your DNS."
