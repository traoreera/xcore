# database - Database Connection Module

## Overview

The `database` module provides centralized database connection management using SQLAlchemy. It handles engine creation, session management, and provides the base model class for all database models.

## Module Structure

```
database/
├── __init__.py          # Module exports
└── db.py                # SQLAlchemy engine, session, and Base model
```

## Core Components

### Database Engine

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from configurations import Xcorecfg

config = Xcorecfg.from_file("config.json")

# Create engine with connection pooling
engine = create_engine(
    config.database.url,
    echo=config.database.echo,
    pool_size=config.database.pool_size,
    max_overflow=config.database.max_overflow,
    pool_timeout=config.database.pool_timeout,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True  # Verify connections before use
)
```

### Session Management

```python
# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base model class
Base = declarative_base()
```

### FastAPI Dependency

```python
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db() -> Session:
    """
    FastAPI dependency for database sessions.

    Yields a database session and ensures proper cleanup.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Async Support

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Async engine
async_engine = create_async_engine(
    config.database.url.replace("sqlite://", "sqlite+aiosqlite://"),
    echo=config.database.echo,
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_async_db() -> AsyncSession:
    """Async database session dependency"""
    async with AsyncSessionLocal() as session:
        yield session
```

## Usage Examples

### Basic Model Definition

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    posts = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    author = relationship("User", back_populates="posts")
```

### CRUD Operations

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database.db import get_db
from .models import User
from .schemas import UserCreate, UserRead

app = FastAPI()

# Create
@app.post("/users/", response_model=UserRead)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Read
@app.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Update
@app.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in user_data.dict().items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user

# Delete
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
```

### Async CRUD Operations

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.db import get_async_db
from .models import User

app = FastAPI()

@app.get("/users/")
async def get_users(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

@app.post("/users/")
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_db)
):
    user = User(**user_data.dict())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

### Database Transactions

```python
from sqlalchemy.orm import Session
from database.db import get_db

def transfer_funds(
    from_account: int,
    to_account: int,
    amount: float,
    db: Session = Depends(get_db)
):
    try:
        # Start transaction
        from_acc = db.query(Account).filter(Account.id == from_account).first()
        to_acc = db.query(Account).filter(Account.id == to_account).first()

        from_acc.balance -= amount
        to_acc.balance += amount

        db.commit()  # Commit transaction
        return {"status": "success"}
    except Exception as e:
        db.rollback()  # Rollback on error
        raise HTTPException(status_code=400, detail=str(e))
```

### Query Examples

```python
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

# Basic query
users = db.query(User).all()

# Filter
active_users = db.query(User).filter(User.is_active == True).all()

# Multiple filters
users = db.query(User).filter(
    and_(
        User.is_active == True,
        User.created_at > date_threshold
    )
).all()

# OR condition
users = db.query(User).filter(
    or_(
        User.email == email,
        User.username == username
    )
).first()

# Join with relationship
posts_with_authors = db.query(Post).options(
    joinedload(Post.author)
).all()

# Aggregation
user_count = db.query(func.count(User.id)).scalar()

# Pagination
users = db.query(User).offset(20).limit(10).all()

# Sorting
users = db.query(User).order_by(User.created_at.desc()).all()

# Distinct
emails = db.query(User.email).distinct().all()

# Group by
role_counts = db.query(
    User.role,
    func.count(User.id)
).group_by(User.role).all()
```

## Configuration

Configuration in `config.json`:

```json
{
  "database": {
    "url": "sqlite:///./app.db",
    "echo": false,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30
  }
}
```

### Database URL Formats

```python
# SQLite
"sqlite:///./app.db"                    # Relative path
"sqlite:////absolute/path/app.db"       # Absolute path
"sqlite:///:memory:"                     # In-memory

# PostgreSQL
"postgresql://user:password@localhost/dbname"
"postgresql+psycopg2://user:password@localhost/dbname"
"postgresql+asyncpg://user:password@localhost/dbname"  # Async

# MySQL
"mysql://user:password@localhost/dbname"
"mysql+pymysql://user:password@localhost/dbname"
"mysql+aiomysql://user:password@localhost/dbname"      # Async
```

## Database Utilities

### Create Tables

```python
from database.db import Base, engine

# Create all tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Create specific table
def init_specific_table():
    User.__table__.create(bind=engine, checkfirst=True)
```

### Drop Tables

```python
from database.db import Base, engine

# Drop all tables
def drop_db():
    Base.metadata.drop_all(bind=engine)

# Drop specific table
def drop_specific_table():
    User.__table__.drop(bind=engine, checkfirst=True)
```

### Check Table Exists

```python
from sqlalchemy import inspect

def table_exists(table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()
```

### Database Migrations

Use Alembic for database migrations (configured in `alembic/`):

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Show current version
alembic current
```

## Testing

### Test Database Setup

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
```

### Using Test Database

```python
@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

def test_create_user(client):
    response = client.post("/users/", json={
        "email": "test@example.com",
        "username": "testuser"
    })
    assert response.status_code == 200
```

## Best Practices

### 1. Always Use Dependency Injection

```python
# Good
@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# Bad - creating session manually
def get_users():
    db = SessionLocal()  # Don't do this
    return db.query(User).all()
```

### 2. Handle Session Cleanup

```python
# Good - session is properly closed
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Good - using context manager
with SessionLocal() as db:
    users = db.query(User).all()
```

### 3. Use Explicit Commits

```python
# Good - explicit commit
def create_user(db: Session, user_data: dict):
    user = User(**user_data)
    db.add(user)
    db.commit()  # Explicit commit
    db.refresh(user)
    return user
```

### 4. Handle Transactions Properly

```python
# Good - proper error handling
def update_user(db: Session, user_id: int, data: dict):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        for key, value in data.items():
            setattr(user, key, value)

        db.commit()
        return user
    except Exception:
        db.rollback()
        raise
```

## Troubleshooting

### Common Issues

1. **Connection pool exhausted**
   - Increase `pool_size` or `max_overflow`
   - Check for unclosed sessions
   - Reduce query execution time

2. **Deadlock errors**
   - Use consistent lock ordering
   - Keep transactions short
   - Add retry logic

3. **Slow queries**
   - Add indexes for filtered columns
   - Use `joinedload` for relationships
   - Implement pagination

4. **Serialization errors**
   - Ensure proper session closure
   - Use `expire_on_commit=False` for async

## Dependencies

- `sqlalchemy` - Database ORM
- `configurations` - Database configuration
- Database drivers:
  - `sqlite3` (built-in)
  - `psycopg2` (PostgreSQL)
  - `pymysql` (MySQL)
  - `aiosqlite` (Async SQLite)
  - `asyncpg` (Async PostgreSQL)

## Related Documentation

- [configurations.md](configurations.md) - Database configuration
- [tools.md](tools.md) - Migration utilities
