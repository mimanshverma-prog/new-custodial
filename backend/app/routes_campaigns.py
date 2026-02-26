from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .models import SessionLocal, Campaign, Contact, SendingLog
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
import time
import os

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
    """Lists all campaigns."""
    campaigns = db.query(Campaign).offset(skip).limit(limit).all()
    return campaigns

@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

# -----------------
# SENDING LOGIC
# -----------------

def send_email_task(campaign_id: int):
    """Sync task to send emails."""

    # Need new session in background task
    db = SessionLocal()

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

        # Establish connection once per batch (or handle per email for better error handling)
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # server.set_debuglevel(1) # Uncomment for debug

                for contact in contacts:
                    # Check if already sent to this contact for this campaign
                    existing_log = db.query(SendingLog).filter(
                        SendingLog.campaign_id == campaign_id,
                        SendingLog.contact_id == contact.id
                    ).first()

                    if existing_log and existing_log.status == "sent":
                        continue # Skip if already sent

                    msg = MIMEMultipart()
                    msg['From'] = "marketing@yourdomain.com" # TODO: Make configurable
                    msg['To'] = contact.email
                    msg['Subject'] = campaign.subject

                    # Simple template replacement
                    body_content = campaign.body.replace("{{name}}", contact.name if contact.name else "")
                    msg.attach(MIMEText(body_content, 'html'))

                    # Create log entry FIRST (status sending)
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

                    try:
                        server.send_message(msg)
                        log_entry.status = "sent"
                        sent_count += 1
                        # print(f"Sent to {contact.email}")
                    except Exception as e:
                        log_entry.status = "failed"
                        log_entry.error_message = str(e)
                        failed_count += 1
                        # print(f"Failed to {contact.email}: {e}")

                    db.commit()

                    # Rate Limiting
                    time.sleep(delay)

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
