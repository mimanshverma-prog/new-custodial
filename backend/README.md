# Setup Project Structure & Backend Skeleton

This step involves initializing the Python project with FastAPI and creating the necessary directory structure for both frontend and backend.

### Actions Taken:
1.  **Project Initialization:**
    -   Created a `backend` directory.
    -   Created `backend/app`, `backend/static`, and `backend/templates` for application code, static assets, and templates respectively.
    -   Created `backend/requirements.txt` with essential dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `aiosmtplib`, `jinja2`, `python-multipart`, and `aiofiles`.

2.  **Database Models:**
    -   Created `backend/app/models.py`.
    -   Configured SQLite database using SQLAlchemy.
    -   Defined three main models:
        -   `Contact`: Stores recipient details (id, email, name, unsubscribed status, creation date).
        -   `Campaign`: Stores campaign details (id, name, subject, body, status, creation date).
        -   `SendingLog`: Tracks email sending attempts (id, campaign_id, contact_id, status, error message, sent date).
    -   Added a `init_db` function to create tables.

3.  **Core Application Logic (Skeleton):**
    -   Created `backend/app/main.py`.
    -   Initialized the FastAPI application.
    -   Set up database initialization on startup.
    -   Added a basic root endpoint (`/`) to verify the server is running.
    -   Included a dependency `get_db` for database session management.

### Verification:
-   Running `python backend/app/main.py` (after installing requirements) should start the server and create the `bulk_mailer.db` file with the defined tables.

The skeleton is now ready for implementing the core logic for contact management, campaign creation, and the sending engine.
