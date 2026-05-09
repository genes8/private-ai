"""Create admin user and seed 3 test documents."""

import uuid
from datetime import UTC, datetime

import bcrypt
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.db.models import Document, IngestionStatus, User, UserRole


def seed() -> None:
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    try:
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            email="admin@safe4ai.local",
            password_hash=bcrypt.hashpw(b"ChangeMe!2024Pilot", bcrypt.gensalt()).decode(),
            role=UserRole.admin,
        )
        db.merge(admin)

        for i in range(1, 4):
            doc = Document(
                id=str(uuid.uuid4()),
                filename=f"test-document-{i}.pdf",
                storage_filename=f"test-document-{i}-{uuid.uuid4()}.pdf",
                file_type="pdf",
                ingestion_status=IngestionStatus.pending,
                uploaded_by=admin_id,
                uploaded_at=datetime.now(UTC),
            )
            db.add(doc)

        db.commit()
        print("Seed complete: admin user + 3 test documents created.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
