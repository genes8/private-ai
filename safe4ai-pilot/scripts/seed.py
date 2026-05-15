"""Create admin user and seed 3 sample policy documents with actual content."""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.db.models import Document, IngestionJob, IngestionJobStatus, IngestionStatus, User, UserRole

_RAW_DIR = Path("data/raw")

_SAMPLE_DOCS = [
    (
        "hr_policy.txt",
        """\
HR Policy Manual — Safe4AI Ltd
================================

1. Annual Leave
---------------
All full-time employees are entitled to 20 days of paid annual leave per calendar year.
Part-time employees receive leave on a pro-rata basis calculated from their contracted hours.
Leave must be approved by the employee's line manager at least 5 working days in advance.
Unused leave may be carried over up to a maximum of 5 days into the following calendar year.
Employees who have not taken their full entitlement by 31 March of the following year will
forfeit the remaining balance unless exceptional circumstances are agreed with HR.

2. Sick Leave
-------------
Employees are entitled to up to 10 days of paid sick leave per year.
A medical certificate is required for absences exceeding 3 consecutive days.
Sick leave does not carry over and resets at the start of each calendar year.

3. Parental Leave
-----------------
Primary caregivers are entitled to 26 weeks of paid parental leave at full salary.
Secondary caregivers are entitled to 4 weeks of paid parental leave.
Notice must be provided at least 6 weeks before the expected start of leave.

4. Public Holidays
------------------
Employees are entitled to all national public holidays in addition to annual leave.
When a public holiday falls on a weekend, the following Monday is observed.
""",
    ),
    (
        "finance_policy.txt",
        """\
Finance and Procurement Policy — Safe4AI Ltd
=============================================

1. Capital Expenditure Approval Matrix
---------------------------------------
All capital expenditure (CapEx) must follow the approval process below:

  Up to €5,000         — Department Manager
  €5,001 – €20,000     — Director of Finance
  €20,001 – €50,000    — Chief Financial Officer (CFO) and CEO
  Over €50,000         — CFO, CEO, and Board of Directors approval required

Requests must be submitted via the procurement portal with a full business case,
ROI analysis, and at least two competitive quotes for amounts over €10,000.

2. Operating Expenditure
------------------------
Operating expenditure (OpEx) up to €2,000 can be approved by cost-centre owners.
Expenses above this threshold require Finance approval before commitment.

3. Expense Reimbursement
------------------------
Employee expenses must be submitted within 30 days of being incurred.
Receipts are mandatory for all individual items over €25.
Travel expenses are reimbursed at published HMRC approved mileage rates.

4. Budget Management
--------------------
Budget holders must ensure expenditure does not exceed approved budgets.
Variance reports are reviewed monthly by the Finance team.
Budget revisions require CFO approval and must be documented.
""",
    ),
    (
        "it_policy.txt",
        """\
IT Security Policy — Safe4AI Ltd
==================================

1. Password Requirements
------------------------
All user accounts must comply with the following password standards:

  - Minimum length: 12 characters
  - Must contain at least one uppercase letter (A–Z)
  - Must contain at least one lowercase letter (a–z)
  - Must contain at least one digit (0–9)
  - Must contain at least one special character (e.g. !@#$%^&*)
  - Passwords must not contain the employee's name or username
  - Passwords must not be reused from the previous 12 passwords
  - Passwords expire every 90 days for privileged accounts

Multi-factor authentication (MFA) is mandatory for all remote access,
administrative accounts, and access to sensitive data systems.

2. Device Security
------------------
All company devices must have full-disk encryption enabled.
Automatic screen lock activates after 5 minutes of inactivity.
Employees must not install unauthorised software on company devices.
Lost or stolen devices must be reported to IT Security within 1 hour.

3. Data Handling
----------------
Sensitive data must not be stored on personal devices or unencrypted USB drives.
All data transfers outside the corporate network must use VPN or approved secure channels.
Cloud services not approved by IT must not be used to store or process company data.

4. Incident Reporting
---------------------
All suspected security incidents must be reported to security@safe4ai.local immediately.
Do not attempt to investigate or remediate security incidents independently.
""",
    ),
]


def _generate_seed_admin_password() -> str:
    seed = secrets.token_urlsafe(18)
    return f"{seed}Aa!9"


async def seed() -> None:
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    admin_password = os.getenv("SEED_ADMIN_PASSWORD") or _generate_seed_admin_password()
    try:
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            email="admin@safe4ai.local",
            password_hash=bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode(),
            role=UserRole.admin,
        )
        db.merge(admin)
        db.flush()

        ingestion_tasks: list[tuple[str, str, str, str]] = []

        for filename, content in _SAMPLE_DOCS:
            storage_name = f"{Path(filename).stem}-{uuid.uuid4()}.txt"
            storage_path = _RAW_DIR / storage_name
            storage_path.write_text(content, encoding="utf-8")

            doc_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())

            doc = Document(
                id=doc_id,
                filename=filename,
                storage_filename=storage_name,
                file_type="txt",
                ingestion_status=IngestionStatus.queued,
                uploaded_by=admin_id,
                uploaded_at=datetime.now(UTC),
            )
            job = IngestionJob(id=job_id, document_id=doc_id, status=IngestionJobStatus.pending)
            db.add(doc)
            db.add(job)
            ingestion_tasks.append((doc_id, job_id, str(storage_path), filename))

        db.commit()
        print("Seed complete: admin user + 3 sample policy documents created.")
        print("Admin email: admin@safe4ai.local")
        if os.getenv("SEED_ADMIN_PASSWORD"):
            print("Admin password: value loaded from SEED_ADMIN_PASSWORD")
        else:
            print(f"Admin password: {admin_password}")
    finally:
        db.close()

    # Trigger ingestion for each document (requires Ollama + Qdrant to be running).
    from app.services.ingestion_service import run_ingestion  # noqa: PLC0415

    for doc_id, job_id, file_path, filename in ingestion_tasks:
        print(f"Ingesting {filename}…")
        try:
            await run_ingestion(
                doc_id=doc_id,
                job_id=job_id,
                file_path=file_path,
                filename=filename,
                uploaded_by=admin_id,
            )
            print(f"  ✓ {filename} indexed successfully.")
        except Exception as exc:
            print(f"  ✗ {filename} ingestion failed: {exc}")
            print("    (Re-index from the admin UI once Ollama and Qdrant are ready.)")


if __name__ == "__main__":
    asyncio.run(seed())
