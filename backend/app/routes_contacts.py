from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from .models import SessionLocal, Contact
import csv
import io
import shutil

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/contacts/upload")
async def upload_contacts(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Uploads a CSV file of contacts."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    content = await file.read()
    decoded_content = content.decode("utf-8")

    # Simple CSV parser
    reader = csv.reader(io.StringIO(decoded_content))
    header = next(reader, None) # Skip header row if present

    added_count = 0
    for row in reader:
        if not row: continue # Skip empty rows

        email = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""

        # Check if email exists
        existing = db.query(Contact).filter(Contact.email == email).first()
        if not existing:
            new_contact = Contact(email=email, name=name)
            db.add(new_contact)
            added_count += 1

    db.commit()
    return {"message": f"Successfully added {added_count} contacts."}

@router.get("/contacts")
def list_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lists all contacts with pagination."""
    contacts = db.query(Contact).offset(skip).limit(limit).all()
    return contacts
