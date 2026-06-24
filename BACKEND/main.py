from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from anthropic import Anthropic
import os
import traceback
import logging
import secrets
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

# Load environment variables from .env.local (development) or .env (production)
env_local = Path('.env.local')
if env_local.exists():
    load_dotenv(env_local)
else:
    load_dotenv()

from models import (
    SkillRequest, AgentResponse, Agent, SkillMetadata, ChatMessage, ChatResponse
)
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import uuid4

from agents.claude_agent import ClaudeAgent
from agents.knowledge_agent_kb import KnowledgeBaseAgent as KnowledgeAgent
from agents.agent_registry import AgentRegistry
from agents.router import AgentRouter
from services.azure_storage_service import AzureStorageService
from services.azure_document_intelligence_service import AzureDocumentIntelligenceService
from services.azure_cognitive_search_service import AzureCognitiveSearchService
from services.auth import AuthService, EntraIDValidator
from services.credential_provider import get_credential_provider
from middleware.auth import AuthMiddleware
from database import init_db, get_db, engine
from database import Conversation, Message, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose Azure and HTTP logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)

load_dotenv()

app = FastAPI(
    title="NEXUS Backend",
    description="NEXUS Multi-Agent AI Intelligence Platform Backend",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on app startup"""
    init_db()

# Initialize auth variables (will be set after credential provider is created)
auth_enabled = False
auth_validator = None
auth_service = None

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "https://nexus.azurewebsites.net",
        "https://nexus.azurecontainerapps.io",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

credential_provider = get_credential_provider()

entra_tenant_id = credential_provider.get_entra_tenant_id()
entra_client_id = credential_provider.get_entra_client_id()
entra_client_secret = credential_provider.get_entra_client_secret()

auth_enabled = entra_tenant_id and entra_client_id and entra_client_secret

if auth_enabled:
    try:
        auth_validator = EntraIDValidator(entra_tenant_id, entra_client_id)
        auth_service = AuthService(entra_tenant_id, entra_client_id, entra_client_secret)
    except Exception as e:
        logger.warning(f"Failed to initialize auth services: {e}")
        auth_enabled = False
else:
    logger.info("Azure Entra ID authentication disabled (no credentials found in Key Vault or environment)")

# Add auth middleware first (before other middleware) if auth is enabled
if auth_enabled and auth_validator:
    app.add_middleware(
        AuthMiddleware,
        entra_validator=auth_validator,
        public_routes=["/health", "/auth/login", "/auth/callback"]
    )

# Get Anthropic API key from credential provider (Key Vault or env var fallback)
try:
    api_key = credential_provider.get_anthropic_key()
except ValueError as e:
    logger.error(f"Failed to get Anthropic API key: {e}")
    raise

# Initialize Anthropic client with Azure AI Foundry endpoint
api_endpoint = os.getenv("ANTHROPIC_API_ENDPOINT", "https://ais-sdc-playground.services.ai.azure.com/anthropic/v1")

client = Anthropic(
    api_key=api_key,
    base_url="https://ais-sdc-playground.services.ai.azure.com/anthropic"
)

# Store conversation history per session
conversations = {}

# Initialize agent registry and router
agent_registry = AgentRegistry()
agent_router = None  # Will be initialized after app setup

# Configure Claude agent
claude_config = Agent(
    id="claude",
    name="Claude Assistant",
    description="General purpose AI assistant for conversation and tasks",
    model="claude-haiku-4-5",
    system_prompt="""You are a helpful assistant. Always format responses for readability.

MARKDOWN FORMATTING:
- # Main header, ## Subheader, ### Sub-subheader
- Bullet points: • main point, - sub-point
- **bold** for emphasis, *italic* for secondary emphasis

TABLE RULES - FOLLOW EXACTLY:
When asked for a table, comparison, or structured data:
1. Start with a blank line before the table
2. Write the header row FIRST with column names
3. Then write the separator row with dashes
4. Then write data rows

CORRECT TABLE EXAMPLE:
(blank line above)
| Fighter Jet | Country | Speed | Range | Best For |
|-------------|---------|-------|-------|----------|
| F-16 | USA | Mach 2.0 | 860 km | Cost-effective |
| Rafale | France | Mach 2.0 | 1850 km | Versatility |
| MiG-29 | Russia | Mach 2.25 | 1430 km | Dogfighting |

IMPORTANT:
- ALWAYS include headers in every table
- Headers must come BEFORE the separator row
- Separator row uses | and dashes: |------|------|
- No empty header cells
- Tables must have at least 2 columns and 1 header row

Use tables for: comparisons, specifications, features, data lists, rankings, technical details.
NEVER create tables without headers.""",
    max_tokens=1024,
    temperature=0.7,
    is_active=True
)

claude_skill = SkillMetadata(
    skill_id="claude",
    agent_id="claude",
    name="Claude",
    description="General Q&A and conversation",
    aliases=["general", "chat"]
)

# Register Claude agent
claude_agent = ClaudeAgent(claude_config, client)
agent_registry.register_agent(claude_agent, claude_skill)

# Initialize Azure Services for Knowledge Base Retrieval
# 1. Azure Storage Service (Blob Storage)
storage_service = AzureStorageService()

# 2. Azure Document Intelligence Service (PDF/Document extraction)
doc_intelligence = AzureDocumentIntelligenceService()

# 3. Azure Cognitive Search Service (Indexing and search)
cognitive_search = AzureCognitiveSearchService()

# Status verified

# Configure Knowledge Agent
knowledge_config = Agent(
    id="knowledge",
    name="Knowledge Base Agent",
    description="Search Azure-powered knowledge base and documentation",
    model="claude-haiku-4-5",
    system_prompt="""You are a helpful knowledge base assistant. When given search results from Azure, synthesize them into clear, well-structured responses. Use markdown formatting with headers and bullet points. Be concise and directly address the user's question.""",
    max_tokens=1024,
    temperature=0.7,
    tools=["search"],
    is_active=True
)

knowledge_skill = SkillMetadata(
    skill_id="knowledge",
    agent_id="knowledge",
    name="Knowledge Base",
    description="Search Azure-based knowledge base and documentation",
    aliases=["kb", "search", "docs"]
)

# Register Knowledge Agent (KB agent uses Knowledge Bases, not cognitive search)
knowledge_agent = KnowledgeAgent(knowledge_config, client)
agent_registry.register_agent(knowledge_agent, knowledge_skill)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "auth_enabled": auth_enabled}


@app.get("/auth/login")
async def get_auth_url():
    """
    Get Azure Entra ID login URL

    Returns:
        Dictionary with auth_url for frontend to redirect to
    """
    if not auth_service:
        raise HTTPException(status_code=503, detail="Authentication not configured")

    try:
        state = secrets.token_urlsafe(32)
        redirect_uri = os.getenv(
            "ENTRA_REDIRECT_URI",
            "http://localhost:5173/auth/callback"
        )

        auth_url = auth_service.get_auth_url(
            redirect_uri=redirect_uri,
            state=state
        )

        return {"auth_url": auth_url, "state": state}

    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate login URL")


@app.post("/auth/callback")
async def auth_callback(code: str, state: str = None):
    """
    Handle OAuth callback from Azure Entra ID

    Args:
        code: Authorization code from Entra ID
        state: CSRF protection state (optional for now)

    Returns:
        Dictionary with access_token, refresh_token, and user info
    """
    if not auth_service:
        raise HTTPException(status_code=503, detail="Authentication not configured")

    try:
        redirect_uri = os.getenv(
            "ENTRA_REDIRECT_URI",
            "http://localhost:5173/auth/callback"
        )

        # Exchange code for tokens
        tokens = await auth_service.exchange_code_for_token(code, redirect_uri)

        # Validate token and extract user info
        user_info = await auth_validator.validate_token(tokens["access_token"])

        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "user_id": user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name")
        }

    except ValueError as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authorization code")
    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


def ensure_table_headers(content: str) -> str:
    """
    Ensure markdown tables have proper headers.
    If a table separator row is detected without headers, fix it.
    """
    lines = content.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a table separator row (contains | and dashes)
        if '|' in line and '-' in line and i > 0:
            prev_line = lines[i-1]
            # If previous line is data (not headers), we need to reconstruct
            if prev_line.strip() and '|' in prev_line and not all(c in '|-' for c in prev_line.replace(' ', '')):
                # This looks like a data row before separator, which means headers are missing
                # Keep going - just ensure the separator is there
                if i + 1 < len(lines) and '|' in lines[i + 1]:
                    # There's a data row after separator, this is a malformed table
                    # Skip and continue - markdown will still render it
                    pass

        result.append(line)
        i += 1

    return '\n'.join(result)


async def generate_conversation_title(bot_response: str) -> str:
    """
    Generate a short, meaningful title for a conversation based on the bot's first response.

    Args:
        bot_response: The bot's first response to the user

    Returns:
        A generated title string (2-4 words)
    """
    try:
        truncated_response = bot_response[:300] if len(bot_response) > 300 else bot_response
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

        response = client.messages.create(
            model=model,
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": f"Based on this response, generate a concise 2-4 word chat title that summarizes the main topic. Remove any markdown, symbols, or special characters.\n\nResponse: \"{truncated_response}\"\n\nRespond with ONLY the title, nothing else."
                }
            ]
        )

        title = response.content[0].text.strip()
        # Clean up any remaining special characters
        title = title.strip('"\'.,!?#*_-')

        # Limit length
        if len(title) > 50:
            title = title[:47] + "..."

        logger.info(f"Generated conversation title: {title}")
        return title or "New Conversation"

    except Exception as e:
        fallback = bot_response[:40].strip()
        fallback = fallback.replace("#", "").replace("*", "").replace("_", "").strip()
        if len(bot_response) > 40:
            fallback += "..."
        return fallback or "New Conversation"


@app.post("/chat/message")
async def chat_message(
    message: SkillRequest,
    session_id: str = "default",
    request: Request = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    Send a message and route to appropriate agent.
    Messages are persisted to the database.

    Args:
        message: SkillRequest with content and optional skill_id
        session_id: Session ID for conversation history
        request: FastAPI Request object (injected by FastAPI)
        db: Database session (injected by FastAPI)

    Returns:
        AgentResponse from the selected agent
    """
    global agent_router
    if agent_router is None:
        agent_router = AgentRouter(agent_registry)

    try:
        # Extract user_id from auth middleware if available
        user_id = getattr(request.state, "user_id", None) if request else None
        user_email = getattr(request.state, "user_email", None) if request else None

        # If auth is enabled, require user_id
        if auth_enabled and not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # If auth is disabled, use guest user
        if not user_id and not auth_enabled:
            user_id = "guest"
            user_email = "guest@localhost"

        # Get or create user in database (always use database when we have user_id)
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                user = User(id=user_id, email=user_email or "unknown")
                db.add(user)
                db.commit()

            # Get or create conversation
            conversation = db.query(Conversation).filter_by(
                id=session_id,
                user_id=user_id
            ).first()

            if not conversation:
                conversation = Conversation(
                    id=session_id,
                    user_id=user_id,
                    title="Conversation"
                )
                db.add(conversation)
                db.commit()
                logger.debug(f"Created conversation: {session_id}")
            else:
                logger.debug(f"Using conversation: {session_id}")

            # Store user message in database
            user_msg = Message(
                id=str(uuid4()),
                conversation_id=conversation.id,
                role="user",
                content=message.content
            )
            db.add(user_msg)
            db.commit()

            # Refresh conversation to get updated messages count
            db.refresh(conversation)

            # Prepare session context with conversation history from database
            messages_list = [
                {"role": m.role, "content": m.content, "agent_id": m.agent_id}
                for m in conversation.messages
            ]
        else:
            # Fallback to in-memory storage (only if no user_id at all)
            if session_id not in conversations:
                conversations[session_id] = []

            conversations[session_id].append({
                "role": "user",
                "content": message.content,
                "timestamp": datetime.now().isoformat()
            })

            messages_list = conversations.get(session_id, [])

        # Extract team membership status from auth middleware if available
        is_team_member = getattr(request.state, "is_team_member", False) if request else False

        session_context = {
            "session_id": session_id,
            "user_id": user_id,
            "user_email": user_email,
            "is_team_member": is_team_member,
            "messages": messages_list
        }

        # Route to appropriate agent
        target_agent = await agent_router.route(
            content=message.content,
            session_context=session_context,
            explicit_skill_id=message.skill_id
        )

        # Process via agent
        agent_response = await target_agent.process(
            content=message.content,
            session_context=session_context,
            parameters=message.parameters
        )

        # Store agent response in database (if we have a user_id/conversation)
        is_first_message = False
        generated_title = None

        if user_id and 'conversation' in locals():
            is_first_message = len(conversation.messages) == 1

            assistant_msg = Message(
                id=str(uuid4()),
                conversation_id=conversation.id,
                role="assistant",
                content=agent_response.content,
                agent_id=agent_response.agent_id
            )
            db.add(assistant_msg)

            # If first message, generate title from bot response
            if is_first_message:
                generated_title = await generate_conversation_title(agent_response.content)
                logger.debug(f"Generated title: {generated_title}")
                conversation.title = generated_title

            conversation.updated_at = datetime.utcnow()
            db.commit()
        else:
            # In-memory storage fallback
            conversations[session_id].append({
                "role": "assistant",
                "content": agent_response.content,
                "agent_id": agent_response.agent_id,
                "agent_name": agent_response.agent_name,
                "timestamp": datetime.now().isoformat(),
                "metadata": agent_response.metadata
            })

        # Create response with generated title if available
        response_data = {
            "content": agent_response.content,
            "role": agent_response.agent_id or "assistant",
            "agent_id": agent_response.agent_id,
            "agent_name": agent_response.agent_name,
            "message_type": agent_response.message_type,
            "metadata": agent_response.metadata,
            "generated_title": generated_title
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error in chat_message: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/conversations")
async def list_conversations(
    request: Request = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    List all conversations for authenticated user.

    Returns:
        Dictionary with list of conversations and metadata
    """
    try:
        # Extract user_id from auth middleware (or use guest if auth disabled)
        user_id = getattr(request.state, "user_id", None) if request else None

        # If auth is disabled, use guest user
        if not user_id:
            user_id = "guest" if not auth_enabled else None

        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Get all conversations for this user
        user_convs = db.query(Conversation).filter_by(
            user_id=user_id
        ).order_by(Conversation.updated_at.desc()).all()

        conversations_data = [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "message_count": len(c.messages)
            }
            for c in user_convs
        ]

        return {
            "status": "success",
            "count": len(conversations_data),
            "conversations": conversations_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents() -> list[SkillMetadata]:
    """
    List all available agents/skills

    Returns:
        List of SkillMetadata for all available agents
    """
    return agent_registry.list_skills()


@app.get("/agents/{agent_id}")
async def get_agent_details(agent_id: str) -> Agent:
    """
    Get details for a specific agent

    Args:
        agent_id: The agent ID

    Returns:
        Agent configuration
    """
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent.config


@app.get("/chat/history")
async def get_chat_history(
    session_id: str = "default",
    request: Request = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get conversation history for a session.
    Filters by user_id if authenticated.

    Args:
        session_id: The session ID
        request: FastAPI Request object (injected by FastAPI)
        db: Database session (injected by FastAPI)

    Returns:
        Dictionary with messages list
    """
    try:
        # Extract user_id if authenticated (or use guest if auth disabled)
        user_id = getattr(request.state, "user_id", None) if request else None

        # If auth is disabled, use guest user
        if not user_id and not auth_enabled:
            user_id = "guest"

        if user_id:
            # Database lookup for authenticated user
            conversation = db.query(Conversation).filter_by(
                id=session_id,
                user_id=user_id
            ).first()

            if not conversation:
                return {"messages": []}

            messages_list = [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "agent_id": m.agent_id,
                    "created_at": m.created_at.isoformat()
                }
                for m in conversation.messages
            ]
            return {"messages": messages_list}
        else:
            # In-memory storage for non-authenticated
            if session_id not in conversations:
                return {"messages": []}
            return {"messages": conversations[session_id]}

    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/clear")
async def clear_chat_history(
    session_id: str = "default",
    request: Request = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    Clear conversation history for a session.
    User-scoped deletion if authenticated.

    Args:
        session_id: The session ID
        request: FastAPI Request object (injected by FastAPI)
        db: Database session (injected by FastAPI)

    Returns:
        Success message
    """
    try:
        # Extract user_id if authenticated (or use guest if auth disabled)
        user_id = getattr(request.state, "user_id", None) if request else None

        # If auth is disabled, use guest user
        if not user_id and not auth_enabled:
            user_id = "guest"

        if user_id:
            # Database deletion for authenticated user
            conversation = db.query(Conversation).filter_by(
                id=session_id,
                user_id=user_id
            ).first()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            db.delete(conversation)
            db.commit()
        else:
            # In-memory storage for non-authenticated
            if session_id in conversations:
                conversations[session_id] = []

        return {"status": "cleared", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/chat/rename")
async def rename_conversation(
    session_id: str = "default",
    new_title: str = "Conversation",
    request: Request = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    Rename a conversation.
    User-scoped update if authenticated.

    Args:
        session_id: The session ID
        new_title: New conversation title
        request: FastAPI Request object (injected by FastAPI)
        db: Database session (injected by FastAPI)

    Returns:
        Success message with updated conversation
    """
    try:
        # Extract user_id if authenticated (or use guest if auth disabled)
        user_id = getattr(request.state, "user_id", None) if request else None

        # If auth is disabled, use guest user
        if not user_id and not auth_enabled:
            user_id = "guest"

        if user_id:
            # Database update for authenticated user
            conversation = db.query(Conversation).filter_by(
                id=session_id,
                user_id=user_id
            ).first()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            conversation.title = new_title.strip()
            conversation.updated_at = datetime.utcnow()
            db.commit()

            return {
                "status": "renamed",
                "session_id": session_id,
                "new_title": conversation.title
            }
        else:
            # In-memory storage for non-authenticated
            if session_id in conversations:
                # Store title metadata (not used by in-memory, but for compatibility)
                return {"status": "renamed", "session_id": session_id, "new_title": new_title}
            raise HTTPException(status_code=404, detail="Conversation not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/upload")
async def upload_knowledge(
    title: str,
    content: str,
    source: str = "manual_upload"
) -> dict:
    """
    Upload a document to the knowledge base

    Args:
        title: Document title
        content: Document content
        source: Source URL or identifier

    Returns:
        Document ID and status
    """
    try:
        doc_id = await hybrid_search.add_document(
            content=content,
            title=title,
            source=source
        )

        if not doc_id:
            raise HTTPException(status_code=500, detail="Failed to save document")

        return {
            "status": "success",
            "doc_id": doc_id,
            "title": title,
            "message": f"Document '{title}' uploaded successfully"
        }

    except Exception as e:
        logger.error(f"Knowledge upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/documents")
async def list_knowledge_documents() -> dict:
    """
    List all documents in the knowledge base

    Returns:
        List of documents with metadata
    """
    try:
        documents = await hybrid_search.list_documents()
        return {
            "status": "success",
            "count": len(documents),
            "documents": documents
        }

    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/knowledge/documents/{doc_id}")
async def delete_knowledge_document(doc_id: str) -> dict:
    """
    Delete a document from the knowledge base

    Args:
        doc_id: Document ID to delete

    Returns:
        Success status
    """
    try:
        success = await hybrid_search.delete_document(doc_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

        return {
            "status": "success",
            "doc_id": doc_id,
            "message": f"Document '{doc_id}' deleted successfully"
        }

    except Exception as e:
        logger.error(f"Delete document error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/clear")
async def clear_knowledge_base() -> dict:
    """
    Clear all documents from the knowledge base (use with caution!)

    Returns:
        Confirmation message
    """
    try:
        await hybrid_search.clear_all()
        return {
            "status": "success",
            "message": "Knowledge base cleared"
        }

    except Exception as e:
        logger.error(f"Clear knowledge base error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/sync-to-azure")
async def sync_to_azure(request: Request) -> dict:
    """
    Sync local knowledge bases to Azure Cognitive Search

    Requires authentication if enabled.

    Returns:
        Sync statistics and status
    """
    if not azure_knowledge_service or not azure_knowledge_service.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Azure Cognitive Search not configured"
        )

    try:
        # Extract user_id from auth middleware if available
        user_id = getattr(request.state, "user_id", None) if request else None

        logger.info(f"Starting knowledge base sync to Azure (user: {user_id})")

        # Get KB services path
        kb_services_path = os.path.join(
            os.path.dirname(__file__),
            "knowledge_bases",
            "services"
        )

        # Sync documents
        sync_stats = await azure_knowledge_service.sync_local_to_azure(kb_services_path)

        logger.info(f"Sync completed with stats: {sync_stats}")

        return {
            "status": "success",
            "data": sync_stats,
            "message": f"Synced {sync_stats.get('services_processed', 0)} services and {sync_stats.get('sections_indexed', 0)} sections to Azure"
        }

    except Exception as e:
        logger.error(f"Sync to Azure error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/services")
async def list_knowledge_services():
    """
    List all services with available documents

    Returns:
        List of services with document counts
    """
    try:
        services_with_docs = []

        containers = await storage_service.list_containers()

        for service_id in containers:
            docs = await storage_service.list_documents(service_id)
            services_with_docs.append({
                "service_id": service_id,
                "document_count": len(docs),
                "documents": [
                    {
                        "name": d["name"],
                        "size": d["size"],
                        "uri": d["uri"]
                    }
                    for d in docs
                ]
            })

        return {
            "status": "success",
            "total_services": len(services_with_docs),
            "services": services_with_docs
        }

    except Exception as e:
        logger.error(f"Error listing services: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/index-documents")
async def index_documents_from_storage(service_id: str = Query(...)):
    """
    Index documents from Blob Storage to Cognitive Search

    Args:
        service_id: Service container name (e.g., "ai-attack")

    Returns:
        Indexing status with detailed error logging
    """
    if not cognitive_search or not cognitive_search.is_configured():
        raise HTTPException(status_code=503, detail="Cognitive Search not configured")

    try:
        documents = await storage_service.list_documents(service_id)

        if not documents:
            return {
                "status": "success",
                "service_id": service_id,
                "indexed_count": 0,
                "failed_count": 0,
                "message": f"No documents found in {service_id}"
            }

        indexed_count = 0
        failed_count = 0
        errors = []

        for i, doc in enumerate(documents):
            doc_name = doc.get("name", "unknown")

            try:
                doc_uri = doc.get("uri", "")
                doc_bytes = await storage_service.download_document(service_id, doc_name)

                if not doc_bytes:
                    msg = f"Failed to download {doc_name}"
                    logger.error(msg)
                    errors.append(msg)
                    failed_count += 1
                    continue

                extraction_result = await doc_intelligence.extract_text_from_bytes(
                    doc_bytes,
                    content_type=doc.get("content_type", "application/pdf")
                )

                extracted_text = ""
                images_data = []
                has_visual_content = False

                if extraction_result:
                    extracted_text = extraction_result.get("text", "")
                    images_data = extraction_result.get("images", [])
                    has_visual_content = extraction_result.get("has_visual_content", False)
                else:
                    logger.debug(f"No content extracted from {doc_name}")

                if not extracted_text or not extracted_text.strip():
                    extracted_text = f"Document: {doc_name}\n[Unable to extract text - document may be image-based or encrypted]"

                doc_id = f"{service_id}_{doc_name.replace('.', '_').replace(' ', '_')}"

                success = await cognitive_search.index_document(
                    document_id=doc_id,
                    service_id=service_id,
                    document_name=doc_name,
                    document_path=f"{service_id}/{doc_name}",
                    title=doc_name,
                    content=extracted_text[:100000] if extracted_text else "Content not extracted",
                    file_size=doc.get("size", 0),
                    created_date=doc.get("created"),
                    modified_date=doc.get("modified"),
                    content_type=doc.get("content_type", "application/octet-stream"),
                    document_uri=doc_uri,
                    images_metadata=images_data,
                    has_visual_content=has_visual_content
                )

                if success:
                    logger.debug(f"Indexed: {doc_name}")
                    indexed_count += 1
                else:
                    msg = f"Indexing failed for {doc_name}"
                    logger.error(msg)
                    errors.append(msg)
                    failed_count += 1

            except Exception as e:
                msg = f"Error processing {doc_name}: {str(e)}"
                logger.error(msg)
                errors.append(msg)
                failed_count += 1

        logger.info(f"Indexing complete: {indexed_count}/{len(documents)} documents indexed")

        return {
            "status": "success",
            "service_id": service_id,
            "indexed_count": indexed_count,
            "failed_count": failed_count,
            "total_documents": len(documents),
            "message": f"Indexed {indexed_count}/{len(documents)} documents from {service_id}",
            "errors": errors if errors else None
        }

    except Exception as e:
        logger.error(f"[ERROR] Exception in index_documents_from_storage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/rebuild-index")
async def rebuild_knowledge_index():
    """
    Delete and recreate the knowledge search index with updated schema

    Returns:
        Status of index recreation
    """
    if not cognitive_search or not cognitive_search.is_configured():
        raise HTTPException(status_code=503, detail="Cognitive Search not configured")

    try:
        logger.info("[REBUILD] Starting index rebuild...")

        # Clear existing index
        await cognitive_search.clear_index()
        logger.info("[REBUILD] Cleared existing index")

        # Recreate index with new schema
        cognitive_search._create_index(recreate=True)
        logger.info("[REBUILD] Index recreated with updated schema")

        return {
            "status": "success",
            "message": "Index deleted and recreated with updated schema"
        }
    except Exception as e:
        logger.error(f"[REBUILD] Failed to rebuild index: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/status")
async def get_knowledge_services_status():
    """
    Get status of all Azure knowledge services

    Returns:
        Configuration status for all services
    """
    return {
        "storage": storage_service.get_status(),
        "document_intelligence": doc_intelligence.get_status(),
        "cognitive_search": cognitive_search.get_status(),
        "all_configured": (
            storage_service.is_configured() and
            doc_intelligence.is_configured() and
            cognitive_search.is_configured()
        )
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
