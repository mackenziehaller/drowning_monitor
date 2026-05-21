"""Database tools for storing and retrieving structured drowning case records."""
import hashlib
import json
import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///drowning_cases.db")
_engine = None


class Base(DeclarativeBase):
    pass


class DrowningCase(Base):
    __tablename__ = "drowning_cases"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    uid             = Column(Text, unique=True, nullable=False)  # hash(date + location)
    url             = Column(Text)
    source          = Column(Text)
    date_of_incident = Column(Text)
    location_name   = Column(Text)
    location_type   = Column(Text)   # Beach, River, Pool, Lake, Dam, Ocean, Other
    state           = Column(Text)   # NSW, QLD, VIC, WA, SA, TAS, NT, ACT
    age_group       = Column(Text)   # Infant, Child, Teen, Adult, Senior, Unknown
    gender          = Column(Text)   # Male, Female, Unknown
    outcome         = Column(Text)   # Fatal, Hospitalised, Rescued, Missing, Unknown
    activity        = Column(Text)   # Swimming, Rock Fishing, Boating, Surfing, etc.
    summary         = Column(Text)
    date_fetched    = Column(DateTime, default=datetime.utcnow)
    raw_json        = Column(Text)


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(_engine)
    return _engine


def save_cases(cases: list[dict]) -> dict:
    """Save structured drowning case records to the database.

    Deduplicates by UID (hash of date + location). Falls back to URL if no UID.

    Args:
        cases: List of dicts with structured DrowningCase fields.

    Returns:
        Dict with 'saved', 'skipped', 'total_attempted'.
    """
    engine = _get_engine()
    saved, skipped = 0, 0

    with Session(engine) as session:
        for case in cases:
            # Generate UID from date + location (same as the reference script)
            date_str = case.get("date_of_incident", "")
            location = case.get("location_name", case.get("url", ""))
            uid = hashlib.md5(f"{date_str}_{location}".lower().encode()).hexdigest()

            if session.query(DrowningCase).filter_by(uid=uid).first():
                skipped += 1
                continue

            record = DrowningCase(
                uid=uid,
                url=case.get("url", ""),
                source=case.get("source", ""),
                date_of_incident=date_str,
                location_name=location,
                location_type=case.get("location_type", "Unknown"),
                state=case.get("state", "Unknown"),
                age_group=case.get("age_group", "Unknown"),
                gender=case.get("gender", "Unknown"),
                outcome=case.get("outcome", "Unknown"),
                activity=case.get("activity", "Unknown"),
                summary=case.get("summary", ""),
                date_fetched=datetime.utcnow(),
                raw_json=json.dumps(case),
            )
            session.add(record)
            saved += 1

        session.commit()

    return {"saved": saved, "skipped": skipped, "total_attempted": len(cases)}


def get_recent_cases(limit: int = 50) -> dict:
    """Retrieve recently saved drowning cases from the database."""
    engine = _get_engine()

    with Session(engine) as session:
        records = (
            session.query(DrowningCase)
            .order_by(DrowningCase.date_fetched.desc())
            .limit(limit)
            .all()
        )

    cases = [
        {
            "id": r.id,
            "url": r.url,
            "source": r.source,
            "date_of_incident": r.date_of_incident,
            "location_name": r.location_name,
            "location_type": r.location_type,
            "state": r.state,
            "age_group": r.age_group,
            "gender": r.gender,
            "outcome": r.outcome,
            "activity": r.activity,
            "summary": r.summary,
            "date_fetched": r.date_fetched.isoformat() if r.date_fetched else None,
        }
        for r in records
    ]

    return {"cases": cases, "count": len(cases)}
