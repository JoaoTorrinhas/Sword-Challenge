from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL .env file
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

#engine = create_engine(DATABASE_URL) # Sync engine sqlalchemy
engine = create_async_engine(DATABASE_URL) # Async engine sqlalchemy |echo=True to log SQL queries (debugging)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession) # Async session sqlalchemy, add class_=AsyncSession

# Create all tables (if they don't exist)
#Base.metadata.create_all(bind=engine) # Sync engine sqlalchemy

# Dependency to get the database session
async def get_db():
    async with SessionLocal() as session:
        yield session

# Create all tables async
async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

