import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import logging
from urllib.parse import urlparse, urlunparse
from services.credential_provider import get_credential_provider

# Import models
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime as dt

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=dt.utcnow)
    updated_at = Column(DateTime, default=dt.utcnow, onupdate=dt.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    agent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

logger = logging.getLogger(__name__)


def get_postgres_with_entra_id(database_url: str) -> str:
    """
    Convert PostgreSQL connection string to use Entra ID authentication.

    For Azure Database for PostgreSQL Flexible Server, replaces password with
    an Entra ID token obtained via managed identity.

    Args:
        database_url: Original PostgreSQL connection string

    Returns:
        Modified connection string with Entra ID token as password
    """
    try:
        parsed = urlparse(database_url)

        if not parsed.hostname or not parsed.hostname.endswith(".postgres.database.azure.com"):
            logger.warning("Not an Azure PostgreSQL database; using password-based auth")
            return database_url

        # Get credential provider
        credential_provider = get_credential_provider()
        azure_credential = credential_provider.get_azure_credential()

        if not azure_credential:
            logger.warning("Azure credential not available; falling back to connection string")
            return database_url

        # Get Entra ID token for PostgreSQL
        token = azure_credential.get_token("https://ossrdbms-aad.database.windows.net/.default")

        if not token:
            logger.warning("Failed to get Entra ID token; falling back to connection string")
            return database_url

        # Replace password with token in connection string
        # Username format: user@servername
        username = parsed.username
        if username and "@" not in username:
            # Add server name to username if not present
            server_name = parsed.hostname.split(".")[0]
            username = f"{username}@{server_name}"

        # Reconstruct URL with token as password
        modified_url = urlunparse((
            parsed.scheme,
            f"{username}:{token.token}@{parsed.hostname}",
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

        logger.info("✓ Using Entra ID token authentication for PostgreSQL")
        return modified_url

    except Exception as e:
        logger.warning(f"Failed to set up Entra ID auth for PostgreSQL: {e}. Falling back to connection string.")
        return database_url


# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nexus.db")

# Use different configurations for SQLite vs PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration
    # Try to use Entra ID auth for Azure PostgreSQL
    db_url = get_postgres_with_entra_id(DATABASE_URL)

    engine = create_engine(
        db_url,
        pool_pre_ping=True,  # Test connections before using them
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all database tables on startup"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db():
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
