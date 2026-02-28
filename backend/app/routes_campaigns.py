from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .models import SessionLocal, Campaign, Contact, SendingLog
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
import os
import time

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CampaignCreate(BaseModel):
    name: str
    subject: str
    body: str

@router.post("/campaigns")
def create_campaign(campaign: CampaignCreate, db: Session = Depends(get_db)):
    """Creates a new campaign."""
    new_campaign = Campaign(
        name=campaign.name,
        subject=campaign.subject,
        body=campaign.body,
        status="draft"
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    return new_campaign

@router.get("/campaigns")
def list_campaigns(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lists all campaigns with basic stats."""
    campaigns = db.query(Campaign).offset(skip).limit(limit).all()
    result = []
    for c in campaigns:
        sent_count = db.query(SendingLog).filter(SendingLog.campaign_id == c.id, SendingLog.status == 'sent').count()
        opened_count = db.query(SendingLog).filter(SendingLog.campaign_id == c.id, SendingLog.opened_at.isnot(None)).count()

        result.append({
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "status": c.status,
            "sent_count": sent_count,
            "opened_count": opened_count
        })
    return result

@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

# -----------------
# SENDING LOGIC
# -----------------

async def send_email_task(campaign_id: int):
    """Async task to send emails with aiosmtplib and tracking injection."""

    # Need new session in background task
    db = SessionLocal()

    # Provide the external URL for tracking pixels and unsubscribe links
    # Default to localhost if not set in docker-compose
    base_url = os.getenv("APP_URL", "http://localhost:8000")

    try:
        # 1. Fetch Campaign Details
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            print(f"Error: Campaign {campaign_id} not found.")
            return

        campaign.status = "sending"
        db.commit()

        # 2. Fetch all contacts (or filter by segment later)
        contacts = db.query(Contact).filter(Contact.unsubscribed == False).all()

        # 3. SMTP Configuration (Localhost for now, will be Postfix later)
        # Using 'localhost' port 25 assumes Postfix is running locally without auth
        smtp_server = os.getenv("SMTP_SERVER", "localhost")
        smtp_port = int(os.getenv("SMTP_PORT", 25))

        # Rate Limiting Configuration
        # Use a safe default (1.0 email/sec) if not set.
        # For warmup, this might be as low as 0.01 (1 email every 100s).
        try:
            emails_per_second = float(os.getenv("EMAILS_PER_SECOND", 1.0))
        except ValueError:
            emails_per_second = 1.0

        delay = 1.0 / emails_per_second if emails_per_second > 0 else 0

        sent_count = 0
        failed_count = 0

        try:
            # Connect asynchronously to Postfix
            smtp_client = aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port)
            await smtp_client.connect()

            for contact in contacts:
                # Check if already sent to this contact for this campaign
                existing_log = db.query(SendingLog).filter(
                    SendingLog.campaign_id == campaign_id,
                    SendingLog.contact_id == contact.id
                ).first()

                if existing_log and existing_log.status == "sent":
                    continue # Skip if already sent

                # Create log entry FIRST (status sending) to get an ID for tracking
                if not existing_log:
                    log_entry = SendingLog(
                        campaign_id=campaign.id,
                        contact_id=contact.id,
                        status="sending"
                    )
                    db.add(log_entry)
                    db.commit()
                    db.refresh(log_entry)
                else:
                    log_entry = existing_log

                msg = MIMEMultipart()
                msg['From'] = "marketing@yourdomain.com" # TODO: Make configurable
                msg['To'] = contact.email
                msg['Subject'] = campaign.subject

                # RFC 8058 One-Click Unsubscribe Headers (MANDATORY FOR GMAIL)
                unsubscribe_url = f"{base_url}/unsubscribe/{contact.id}"
                msg['List-Unsubscribe'] = f"<{unsubscribe_url}>"
                msg['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"

                # Simple template replacement
                body_content = campaign.body.replace("{{name}}", contact.name if contact.name else "")

                # Inject Tracking Pixel and manual unsubscribe link
                tracking_pixel = f'<img src="{base_url}/track/{log_entry.id}.gif" width="1" height="1" alt="" />'
                unsubscribe_footer = f'<br><br><p style="font-size:10px; color:#666;">If you wish to stop receiving these emails, <a href="{unsubscribe_url}">unsubscribe here</a>.</p>'

                final_html = body_content + tracking_pixel + unsubscribe_footer
                msg.attach(MIMEText(final_html, 'html'))

                try:
                    await smtp_client.send_message(msg)
                    log_entry.status = "sent"
                    sent_count += 1
                except Exception as e:
                    log_entry.status = "failed"
                    log_entry.error_message = str(e)
                    failed_count += 1

                db.commit()

                # Rate Limiting (Async sleep)
                if delay > 0:
                    await asyncio.sleep(delay)

            await smtp_client.quit()

            campaign.status = "completed"
            db.commit()
            print(f"Campaign {campaign_id} finished. Sent: {sent_count}, Failed: {failed_count}")

        except Exception as e:
            print(f"SMTP Connection Error or Critical Fail: {e}")
            campaign.status = "failed"
            db.commit()

    finally:
        db.close()

@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger the sending process for a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status == "sending":
        raise HTTPException(status_code=400, detail="Campaign is already sending.")

    # Start background task
    background_tasks.add_task(send_email_task, campaign_id)

    return {"message": "Campaign sending started in background."}
