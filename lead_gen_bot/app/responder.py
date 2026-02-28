import asyncio
import imaplib
import email
from email.header import decode_header
import logging

logger = logging.getLogger(__name__)

class ZoraIMAPListener:
    def __init__(self, imap_accounts: list):
        """
        imap_accounts: List of dicts e.g.,
        [
            {"server": "imap.domain1.com", "port": 993, "user": "sales@domain1.com", "pass": "secret"}
        ]
        """
        self.accounts = imap_accounts

    def _decode_header(self, raw_header):
        decoded_bytes, charset = decode_header(raw_header)[0]
        if isinstance(decoded_bytes, bytes):
            return decoded_bytes.decode(charset or 'utf-8')
        return decoded_bytes

    def _get_email_body(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == 'text/plain':
                    return part.get_payload(decode=True).decode()
        else:
            return msg.get_payload(decode=True).decode()
        return ""

    def process_incoming_emails(self, account):
        """
        Connects to a single IMAP account, searches for unread emails,
        and analyzes keywords for automatic response.
        """
        logger.info(f"Connecting IMAP listener to {account['user']}")
        try:
            mail = imaplib.IMAP4_SSL(account['server'], account['port'])
            mail.login(account['user'], account['pass'])
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages[0]:
                return []

            email_ids = messages[0].split()
            auto_replies_triggered = []

            for eid in email_ids:
                status, data = mail.fetch(eid, "(RFC822)")
                if status != "OK": continue

                msg = email.message_from_bytes(data[0][1])
                sender = self._decode_header(msg.get("From"))
                subject = self._decode_header(msg.get("Subject"))
                body = self._get_email_body(msg).lower()

                # ZORA CORE: Smart Keyword Detection
                if any(kw in body for kw in ["payment gateway", "integration issue", "stripe error", "paypal"]):
                    logger.info(f"Zora Detected Keyword in email from {sender}")
                    # In a fully integrated system, this would call ZoraMailer to send the response.
                    # For now we yield the required auto-response mapping.
                    auto_replies_triggered.append({
                        "to_email": sender,
                        "subject": f"Re: {subject}",
                        "body": "Hi,\n\nI noticed you mentioned payment gateway issues. Our Zora platform has a built-in solution that completely solves this problem seamlessly. Would you be open to a quick 5-minute demo?\n\nBest,\nZora Team",
                        "account": account
                    })

                # Mark as read (implicitly done by FETCH but we can be explicit if needed)

            mail.logout()
            return auto_replies_triggered
        except Exception as e:
            logger.error(f"IMAP Error on {account['user']}: {e}")
            return []

    async def start_listening_loop(self, delay: int = 60):
        """
        Background loop to check all registered IMAP accounts every X seconds.
        """
        logger.info(f"Zora Auto-Responder engine starting. Listening on {len(self.accounts)} accounts.")
        while True:
            for account in self.accounts:
                # Run the blocking IMAP operations in an executor thread
                loop = asyncio.get_event_loop()
                replies_needed = await loop.run_in_executor(None, self.process_incoming_emails, account)

                # If we detected an auto-reply condition, trigger the mailer
                # In production this would queue to a Redis broker or call ZoraMailer directly
                for reply in replies_needed:
                    logger.info(f"Triggering auto-response to {reply['to_email']}")

            # Sleep until next check
            await asyncio.sleep(delay)
