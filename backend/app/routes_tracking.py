from fastapi import APIRouter, Request, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from .models import SessionLocal, Contact, SendingLog
import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------
# RFC 8058 One-Click Unsubscribe (MANDATORY for Gmail/Yahoo)
# -----------------------------------------------------
@router.post("/unsubscribe/{contact_id}")
async def one_click_unsubscribe(contact_id: int, db: Session = Depends(get_db)):
    """Handles the POST request from email clients (Gmail/Yahoo) when users click 'Unsubscribe' in the header."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.unsubscribed = True
    db.commit()
    return {"message": "Unsubscribed successfully"}

@router.get("/unsubscribe/{contact_id}")
async def manual_unsubscribe(contact_id: int, request: Request, db: Session = Depends(get_db)):
    """Handles manual clicks on the unsubscribe link in the email body."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if contact:
        contact.unsubscribed = True
        db.commit()
        return Response(content="<html><body><h1>You have been unsubscribed successfully.</h1></body></html>", media_type="text/html")
    return Response(content="<html><body><h1>Contact not found.</h1></body></html>", status_code=404, media_type="text/html")

# -----------------------------------------------------
# Open Tracking Pixel (Invisible 1x1 GIF)
# -----------------------------------------------------
@router.get("/track/{log_id}.gif")
async def track_open(log_id: int, request: Request, db: Session = Depends(get_db)):
    """Records an 'open' event when the invisible pixel is loaded."""
    log_entry = db.query(SendingLog).filter(SendingLog.id == log_id).first()

    # Only record the first open time
    if log_entry and not log_entry.opened_at:
        log_entry.opened_at = datetime.datetime.utcnow()
        db.commit()

    # Return a 1x1 transparent GIF
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(content=pixel, media_type="image/gif")
