import dns.resolver
import sys

def check_dns(domain):
    print(f"\n🔍 Checking DNS Records for: {domain}\n")
    print("-" * 50)

    resolver = dns.resolver.Resolver()
    resolver.nameservers = ['8.8.8.8'] # Use Google Public DNS

    # 1. Check A Record
    try:
        answers = resolver.resolve(f'mail.{domain}', 'A')
        print(f"✅ A Record found: {answers[0].to_text()} -> mail.{domain}")
    except dns.resolver.NoAnswer:
        print(f"❌ Missing A Record: Ensure you pointed 'mail.{domain}' to your server IP.")
    except Exception as e:
        print(f"❌ Error checking A Record: {e}")

    # 2. Check MX Record
    try:
        answers = resolver.resolve(domain, 'MX')
        mx_records = [rdata.exchange.to_text() for rdata in answers]
        if f"mail.{domain}." in mx_records:
            print(f"✅ MX Record found: Points correctly to mail.{domain}")
        else:
            print(f"⚠️ MX Record found, but points to: {mx_records[0]}. Expected: mail.{domain}")
    except Exception as e:
        print(f"❌ Missing MX Record: No mail server configured for {domain}")

    # 3. Check SPF Record
    try:
        answers = resolver.resolve(domain, 'TXT')
        spf_found = False
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if txt.startswith("v=spf1"):
                print(f"✅ SPF Record found: {txt}")
                spf_found = True
                break
        if not spf_found:
            print(f"❌ Missing SPF Record: Without this, emails go to Spam.")
    except Exception as e:
        print(f"❌ Error checking SPF Record: {e}")

    # 4. Check DKIM Record
    try:
        # Assuming the selector is 'mail' as configured in setup_server.sh
        dkim_domain = f"mail._domainkey.{domain}"
        answers = resolver.resolve(dkim_domain, 'TXT')
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if "v=DKIM1" in txt or "p=" in txt:
                print(f"✅ DKIM Record found for selector 'mail'. Signature present.")
                break
    except Exception as e:
        print(f"❌ Missing DKIM Record: Could not find TXT record at mail._domainkey.{domain}. Check your DNS.")

    # 5. Check DMARC Record
    try:
        dmarc_domain = f"_dmarc.{domain}"
        answers = resolver.resolve(dmarc_domain, 'TXT')
        dmarc_found = False
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if txt.startswith("v=DMARC1"):
                print(f"✅ DMARC Record found: {txt}")
                dmarc_found = True
                break
        if not dmarc_found:
            print(f"❌ Missing DMARC Record: Add a TXT record for _dmarc.{domain}")
    except Exception as e:
        print(f"❌ Error checking DMARC Record: {e}")

    print("-" * 50)
    print("\n💡 Tip: DNS changes can take 15 mins to 24 hours to propagate globally.")
    print("If you just added them, wait an hour and check again.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 check_dns.py <yourdomain.com>")
        sys.exit(1)

    domain = sys.argv[1].lower()
    check_dns(domain)
