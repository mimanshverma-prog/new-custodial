import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import time

logger = logging.getLogger(__name__)

class ZoraMailer:
    def __init__(self, smtp_accounts: list):
        """
        smtp_accounts: List of dicts e.g.,
        [
            {"server": "smtp.domain1.com", "port": 587, "user": "sales@domain1.com", "pass": "secret"},
            {"server": "smtp.domain2.com", "port": 587, "user": "contact@domain2.com", "pass": "secret"}
        ]
        """
        self.accounts = smtp_accounts
        self.current_account_index = 0
        self.emails_sent_current_domain = 0
        self.max_per_domain = 60 # Strict limit to prevent spam flagging

    def get_current_account(self):
        if not self.accounts:
            return None

        # Domain Rotation Logic
        if self.emails_sent_current_domain >= self.max_per_domain:
            self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
            self.emails_sent_current_domain = 0
            logger.info(f"Domain limit reached. Rotating to account: {self.accounts[self.current_account_index]['user']}")

        return self.accounts[self.current_account_index]

    async def send_marketing_email(self, to_email: str, name: str, company: str, subject: str, body: str):
        """
        Sends an email using the active rotated SMTP domain.
        """
        account = self.get_current_account()
        if not account:
            logger.error("No SMTP accounts configured in Zora Mailer!")
            return False

        msg = MIMEMultipart()
        msg['From'] = account['user']
        msg['To'] = to_email
        msg['Subject'] = subject

        # Personalization
        formatted_body = body.replace("{{name}}", name).replace("{{company}}", company)
        msg.attach(MIMEText(formatted_body, 'plain'))

        def _send():
            try:
                # Add delay to simulate human sending and respect provider limits
                time.sleep(2)

                with smtplib.SMTP(account['server'], account['port'], timeout=10) as server:
                    server.starttls()
                    server.login(account['user'], account['pass'])
                    server.send_message(msg)
                return True
            except Exception as e:
                logger.error(f"Failed to send email to {to_email} via {account['user']}: {e}")
                return False

        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, _send)

        if success:
            self.emails_sent_current_domain += 1
            logger.info(f"Successfully sent marketing email to {to_email} via {account['user']} ({self.emails_sent_current_domain}/{self.max_per_domain})")

        return success
