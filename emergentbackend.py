from fastapi import FastAPI, APIRouter, HTTPException, Depends, status``
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage
import aiohttp
from bs4 import BeautifulSoup
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Emergent LLM key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', 'sk-emergent-5266445AeC21d4a2c6')

# Security
security = HTTPBearer()
JWT_SECRET = os.environ.get('JWT_SECRET', 'psa-dashboard-secret-key-2024')
JWT_ALGORITHM = 'HS256'

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class UserRegister(BaseModel):
    username: str
    password: str
    job_title: str
    job_description: str
    region: str = "Singapore"

class UserLogin(BaseModel):
    username: str
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    job_title: str
    job_description: str
    region: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class NewsArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    url: str
    risk_level: str
    analysis: str
    alternate_routes: Optional[List[str]] = None
    measures: Optional[str] = None
    scraped_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# Auth helpers
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0, 'password': 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# News scraping
async def scrape_cna_news():
    """Scrape news from CNA website"""
    articles = []
    urls = [
        'https://www.channelnewsasia.com/singapore',
        'https://www.channelnewsasia.com/business'
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Find article elements
                            article_elements = soup.find_all('h3', class_='card__title')
                            
                            for elem in article_elements[:3]:  # Get top 3 articles
                                link = elem.find('a')
                                if link:
                                    title = link.get_text(strip=True)
                                    article_url = link.get('href', '')
                                    if article_url and not article_url.startswith('http'):
                                        article_url = 'https://www.channelnewsasia.com' + article_url
                                    
                                    articles.append({
                                        'title': title,
                                        'url': article_url,
                                        'content': title  # Using title as content for MVP
                                    })
                except Exception as e:
                    logging.error(f"Error scraping {url}: {e}")
                    continue
    except Exception as e:
        logging.error(f"Error in scraping: {e}")
    
    # Fallback mock data if scraping fails
    if not articles:
        articles = [
            {
                'title': 'Port congestion reported at Tanjong Pagar Terminal',
                'url': 'https://www.channelnewsasia.com/singapore/port-congestion',
                'content': 'Heavy vessel traffic causing delays at Tanjong Pagar Terminal, expected delays of 2-3 hours'
            },
            {
                'title': 'PSA Singapore reports increased cargo volume',
                'url': 'https://www.channelnewsasia.com/business/psa-cargo',
                'content': 'Container throughput increases by 15% this quarter, strain on infrastructure'
            },
            {
                'title': 'Weather warning issued for Singapore Strait',
                'url': 'https://www.channelnewsasia.com/singapore/weather',
                'content': 'Monsoon conditions expected to affect shipping lanes in the next 48 hours'
            }
        ]
    
    return articles

async def analyze_news_with_openai(article: dict, user_context: str):
    """Analyze news article for risk and generate response"""
    prompt = f"""You are a logistics risk analyst for PSA Singapore.
    
User Context: {user_context}

Analyze this news article:
Title: {article['title']}
Content: {article['content']}

Provide:
1. Risk Level (LOW/MEDIUM/HIGH)
2. Brief analysis of impact on port operations
3. If HIGH risk: Provide 3 specific alternate routes with justification
4. If MEDIUM risk: Suggest alternate routes and mitigation measures
5. If LOW risk: Brief informational summary

Format as JSON:
{{
  "risk_level": "HIGH/MEDIUM/LOW",
  "analysis": "detailed analysis",
  "alternate_routes": ["route1", "route2", "route3"] or null,
  "measures": "mitigation measures" or null
}}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"news-{uuid.uuid4()}",
            system_message="You are a logistics risk analyst. Always respond with valid JSON."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        import json
        result = json.loads(response)
        return result
    except Exception as e:
        logging.error(f"OpenAI analysis error: {e}")
        return {
            "risk_level": "MEDIUM",
            "analysis": "Unable to analyze at this time",
            "alternate_routes": None,
            "measures": "Monitor situation closely"
        }

# Auth endpoints
@api_router.post("/auth/register")
async def register(user_data: UserRegister):
    existing = await db.users.find_one({'username': user_data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        username=user_data.username,
        job_title=user_data.job_title,
        job_description=user_data.job_description,
        region=user_data.region
    )
    
    user_doc = user.model_dump()
    user_doc['password'] = hash_password(user_data.password)
    
    await db.users.insert_one(user_doc)
    
    token = create_token(user.id)
    return {"token": token, "user": user.model_dump()}

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({'username': credentials.username})
    if not user_doc or not verify_password(credentials.password, user_doc['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user_doc['id'])
    user_doc.pop('password')
    user_doc.pop('_id')
    
    return {"token": token, "user": user_doc}

@api_router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    return user

# News endpoints
@api_router.get("/news/analyze")
async def analyze_news(user = Depends(get_current_user)):
    # Scrape news
    articles = await scrape_cna_news()
    
    # User context for personalization
    user_context = f"Job: {user['job_title']}, Region: {user['region']}, Description: {user['job_description']}"
    
    # Analyze each article
    analyzed_articles = []
    for article in articles:
        analysis = await analyze_news_with_openai(article, user_context)
        
        news_item = NewsArticle(
            title=article['title'],
            content=article['content'],
            url=article['url'],
            risk_level=analysis['risk_level'],
            analysis=analysis['analysis'],
            alternate_routes=analysis.get('alternate_routes'),
            measures=analysis.get('measures')
        )
        analyzed_articles.append(news_item.model_dump())
    
    return analyzed_articles

# Dashboard metrics
@api_router.get("/dashboard/metrics")
async def get_metrics(user = Depends(get_current_user)):
    """Generate mock PowerBI-style metrics"""
    # Generate realistic port metrics
    current_hour = datetime.now(timezone.utc).hour
    
    # Traffic predictions (next 24 hours)
    traffic_predictions = []
    for i in range(24):
        hour = (current_hour + i) % 24
        # Peak hours: 8-10am and 2-5pm
        if 8 <= hour <= 10 or 14 <= hour <= 17:
            traffic = random.randint(80, 95)
        else:
            traffic = random.randint(40, 70)
        
        traffic_predictions.append({
            'hour': hour,
            'traffic_level': traffic,
            'expected_delay': max(0, (traffic - 70) * 2)  # Delays when >70% capacity
        })
    
    # Port utilization by terminal
    terminals = [
        {'name': 'Tanjong Pagar', 'utilization': random.randint(75, 95), 'vessels': random.randint(12, 18)},
        {'name': 'Keppel', 'utilization': random.randint(60, 85), 'vessels': random.randint(8, 14)},
        {'name': 'Brani', 'utilization': random.randint(50, 75), 'vessels': random.randint(6, 12)},
        {'name': 'Pasir Panjang', 'utilization': random.randint(70, 90), 'vessels': random.randint(10, 16)}
    ]
    
    # Delay statistics
    delays = {
        'average_delay_minutes': random.randint(25, 45),
        'max_delay_today': random.randint(90, 180),
        'vessels_delayed': random.randint(5, 15),
        'peak_delay_hour': random.choice([9, 10, 15, 16])
    }
    
    # Cargo volume trends (last 7 days)
    cargo_trends = []
    for i in range(7):
        day = datetime.now(timezone.utc) - timedelta(days=6-i)
        cargo_trends.append({
            'date': day.strftime('%Y-%m-%d'),
            'teu_processed': random.randint(25000, 35000),
            'efficiency': random.randint(85, 98)
        })
    
    return {
        'traffic_predictions': traffic_predictions,
        'terminals': terminals,
        'delays': delays,
        'cargo_trends': cargo_trends,
        'generated_at': datetime.now(timezone.utc).isoformat()
    }

# Business report
@api_router.get("/dashboard/report")
async def generate_report(user = Depends(get_current_user)):
    """Generate AI-powered business report"""
    # Get metrics
    metrics = await get_metrics(user)
    
    prompt = f"""You are a senior logistics analyst at PSA Singapore.

Generate a professional business report for: {user['job_title']} in {user['region']}

Current Metrics:
- Average delay: {metrics['delays']['average_delay_minutes']} minutes
- Terminals operating at 60-95% capacity
- Peak traffic expected at hour {metrics['delays']['peak_delay_hour']}

Create a structured report with:
1. Executive Summary
2. Performance Analysis
3. Problem Areas and Root Causes
4. Recommendations for Future Planning

Use formal business language. Be specific and actionable."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"report-{uuid.uuid4()}",
            system_message="You are a senior logistics analyst. Write formal business reports."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return {
            'report': response,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'metrics_snapshot': metrics
        }
    except Exception as e:
        logging.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")

# Chatbot
@api_router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, user = Depends(get_current_user)):
    """General chatbot for user queries"""
    system_prompt = f"""You are an AI assistant for PSA Singapore port operations.

User Profile:
- Name: {user['username']}
- Role: {user['job_title']}
- Region: {user['region']}
- Responsibilities: {user['job_description']}

Assume the user has basic knowledge of their job scope. Provide helpful, specific answers about port operations, logistics, shipping, and related topics. Be professional and concise."""

    try:
        chat_session = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"chat-{user['id']}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=message.message)
        response = await chat_session.send_message(user_message)
        
        return ChatResponse(response=response)
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Chat service unavailable")

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()