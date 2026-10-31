"""Durable uploads/runs and versioned SQL records (SQLite or PostgreSQL)."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Text, select
from config import settings

def data_dir():
    path = Path(settings.DATA_DIR).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

def identity(value):
    return str(uuid.UUID(str(value)))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def upload_path(file_id):
    file_id = identity(file_id)
    for folder in [data_dir() / 'raw_invoices', Path(__file__).resolve().parents[2] / 'data/raw_invoices']:
        for ext in ['jpg', 'png', 'jpeg']:
            path = folder / f'{file_id}.{ext}'
            if path.is_file():
                return path
    raise FileNotFoundError('Upload not found; upload the document first.')

def load_image(file_id):
    return upload_path(file_id).read_bytes()

def save_run(value):
    run_id = str(uuid.uuid4())
    value = {**value, 'run_id': run_id, 'created_at': datetime.now(timezone.utc).isoformat()}
    write_json(data_dir() / 'runs' / f'{run_id}.json', value)
    return value

def load_run(run_id):
    return json.loads((data_dir() / 'runs' / f'{identity(run_id)}.json').read_text(encoding='utf-8'))

metadata = MetaData()
versions = Table('emunim_schema_versions', metadata, Column('version', Integer, primary_key=True))
documents = Table('emunim_documents', metadata,
    Column('id', String(36), primary_key=True), Column('run_id', String(36), unique=True, nullable=False),
    Column('created_at', String(40), nullable=False), Column('doc_type', String(40), nullable=False),
    Column('payload', Text, nullable=False))

@lru_cache(maxsize=4)
def database(url):
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    engine = create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}))
    # Additive migration v1. Future changes must add explicit versioned migrations.
    metadata.create_all(engine)
    with engine.begin() as conn:
        if conn.execute(select(versions.c.version)).first() is None:
            conn.execute(versions.insert().values(version=1))
    return engine

def engine():
    return database(settings.DATABASE_URL or f'sqlite:///{(data_dir() / "emunim.db").as_posix()}')

def list_records():
    with engine().connect() as conn:
        rows = conn.execute(select(documents.c.payload).order_by(documents.c.created_at.desc())).scalars()
        return [json.loads(row) for row in rows]

def insert_record(record):
    with engine().begin() as conn:
        existing = conn.execute(select(documents.c.payload).where(documents.c.run_id == record['run_id'])).scalar_one_or_none()
        if existing:
            return json.loads(existing)
        conn.execute(documents.insert().values(id=record['id'], run_id=record['run_id'], created_at=record['created_at'], doc_type=record['doc_type'], payload=json.dumps(record)))
    return record
