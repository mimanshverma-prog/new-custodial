import asyncio
import dns.resolver
import smtplib
import socket
import logging
from typing import List, Tuple, Optional
from email_validator import validate_email, EmailNotValidError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailVerifier:
    def __init__(self):
        self.personal_domains = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'live.com', 'aol.com'}

    def generate_email_patterns(self, name: str, domain: str) -> List[str]:
        """
        Generates common B2B email patterns based on a person's name and company domain.
        """
        if not name or not domain:
            return []

        parts = name.lower().split()
        if len(parts) < 2:
            first = parts[0]
            return [
                f"{first}@{domain}",
                f"{first[0]}@{domain}"
            ]

        first = parts[0]
        last = parts[-1]

        # Clean up any non-alphanumeric characters
        first = ''.join(e for e in first if e.isalnum())
        last = ''.join(e for e in last if e.isalnum())

        patterns = [
            f"{first}.{last}@{domain}",    # john.doe@company.com
            f"{first[0]}{last}@{domain}",    # jdoe@company.com
            f"{first}@{domain}",             # john@company.com
            f"{first}_{last}@{domain}",    # john_doe@company.com
            f"{first}{last[0]}@{domain}",    # johnd@company.com
            f"{last}.{first}@{domain}"     # doe.john@company.com
        ]

        # Deduplicate while preserving order
        return list(dict.fromkeys(patterns))

    async def get_mx_records(self, domain: str) -> List[str]:
        """
        Retrieves MX records for a given domain to find its mail servers.
        """
        try:
            loop = asyncio.get_event_loop()
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5

            # Run DNS query in thread pool
            answers = await loop.run_in_executor(None, resolver.resolve, domain, 'MX')

            records = [str(rdata.exchange).rstrip('.') for rdata in answers]
            # Sort by priority (which dns.resolver does automatically, but we just take the list)
            return records
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout) as e:
            logger.debug(f"No MX records found for {domain}: {e}")
            return []
        except Exception as e:
            logger.debug(f"DNS error for {domain}: {e}")
            return []

    async def verify_smtp(self, email: str, mx_record: str) -> bool:
        """
        Performs an SMTP handshake to check if the email address actually exists.
        """
        domain = email.split('@')[1]

        def smtp_check():
            try:
                # Set a timeout for the SMTP connection
                server = smtplib.SMTP(timeout=5)
                # Some servers require EHLO instead of HELO
                server.connect(mx_record)
                server.helo(socket.getfqdn())

                # Use a dummy sender address that looks legitimate
                server.mail(f"ping@{socket.getfqdn()}")

                # Check recipient
                code, _ = server.rcpt(email)
                server.quit()

                # 250: Requested mail action okay, completed
                # 251: User not local; will forward to <forward-path>
                # 252: Cannot VRFY user, but will accept message and attempt delivery
                return code in [250, 251, 252]
            except smtplib.SMTPServerDisconnected:
                logger.debug(f"Server disconnected unexpectedly while checking {email}")
                return False
            except smtplib.SMTPConnectError as e:
                logger.debug(f"Could not connect to SMTP server {mx_record}: {e}")
                return False
            except Exception as e:
                logger.debug(f"SMTP check failed for {email} on {mx_record}: {e}")
                return False

        loop = asyncio.get_event_loop()
        # Run in a separate thread so it doesn't block asyncio loop
        is_valid = await loop.run_in_executor(None, smtp_check)
        return is_valid

    async def find_valid_email(self, name: str, domain: str) -> Tuple[Optional[str], str]:
        """
        Generates patterns and verifies them to find a valid work email.
        Returns a tuple of (Valid_Email_Or_None, Status_String).
        """
        if domain in self.personal_domains:
            return None, "Invalid - Personal Domain"

        patterns = self.generate_email_patterns(name, domain)
        if not patterns:
            return None, "Invalid - Missing Name/Domain"

        # Check basic syntax first
        valid_patterns = []
        for p in patterns:
            try:
                validate_email(p, check_deliverability=False)
                valid_patterns.append(p)
            except EmailNotValidError:
                continue

        mx_records = await self.get_mx_records(domain)
        if not mx_records:
            return None, "Invalid - No MX Records"

        primary_mx = mx_records[0]

        # Test patterns sequentially (testing concurrently might look like spam/DDoS to the MX server)
        for email in valid_patterns:
            logger.info(f"Checking email: {email}")
            is_valid = await self.verify_smtp(email, primary_mx)
            if is_valid:
                return email, "Valid"

            # Add a small delay between checks
            await asyncio.sleep(1)

        return None, "Invalid - Unverifiable"

# Simple manual test
if __name__ == "__main__":
    async def test():
        ev = EmailVerifier()
        email, status = await ev.find_valid_email("Elon Musk", "tesla.com")
        print(f"Result: {email} - {status}")

    asyncio.run(test())
