from fastapi import FastAPI, Depends, HTTPException, status 
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
#from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from models import Patient, Recommendation
from connection_db import get_db, create_all_tables
from typing import List, Optional
from datetime import date, datetime, timedelta
import redis.asyncio as redis 
import json
import jwt
import os
import logging
import asyncio
import bcrypt


# JWT token information
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Redis information
REDIS_HOST = os.getenv("REDIS_HOST") 
REDIS_PORT = os.getenv("REDIS_PORT")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
    
# Request and Response models for json data
class PatientData(BaseModel):
    first_name: str
    last_name: str
    age: int
    bmi: float
    chronic_pain: bool
    recent_surgery: bool

class PatientResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    age: int
    bmi: float
    chronic_pain: bool
    recent_surgery: bool    
    
class RecommendationResponse(BaseModel):
    id: str
    patient_id: int
    recommendation: str
    timestamp: datetime
    
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    #username: str | None = None
    username: Optional[str] = None


# Redis Connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password):
    pwd_bytes = password.encode('utf-8')  
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)  # Hash the password
    return hashed_password


fake_users_db = {
    "username": "admin",
    "password": hash_password("admin123"),
}


# Create all table on startup
@app.on_event("startup")
async def on_startup():
    await create_all_tables()
    
    
def verify_password(plain_password, hashed_password):
    password_byte_enc = plain_password.encode('utf-8')
    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15) # default value
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
        
        
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        if user is None:
            raise credentials_exception
        token_data = TokenData(username=user)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired!")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token!")
    
    if token_data.username != fake_users_db["username"]:
        raise credentials_exception

    return user


def get_recommendations_cache_key(patient_id: int, patient_first_name: str, patient_last_name: str) -> str:
    return f"recommendation:{patient_id}:{patient_first_name}:{patient_last_name}"


def get_recommendations_cache_key_by_id(recommendation_id: str) -> str:
    return f"recommendation:{recommendation_id}"


def generate_recommendation(patient_data: PatientData) -> List[str]:
    recommendations = []
    
    if patient_data.recent_surgery:
        recommendations.append("Post-Op Rehabilitation Plan")
        
    if patient_data.age > 65 and patient_data.chronic_pain:
        recommendations.append("Physical Therapy")
        
    if patient_data.bmi > 30:
        recommendations.append("Weight Management Program")
        
    if not recommendations:
        recommendations.append("General Health Checkup")
    
    return recommendations


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    #logger.info(f"User: {form_data.username} is trying to login with password {form_data.password}") # debug
    
    if form_data.username != fake_users_db["username"] or not verify_password(form_data.password, fake_users_db["password"]):
        raise HTTPException(
            status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"}
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": fake_users_db["username"]}, 
        expires_delta=access_token_expires
    )
    jwt_token = Token(
        access_token=access_token, 
        token_type="bearer"
    )
    return jwt_token


@app.post("/evaluate")
async def evaluate_pacient(
    patient_data: PatientData,
    #db: Session = Depends(get_db)
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):  
    try:
        # Check if patient already exists, i.e, same first_name and last_name
        result = await db.execute(select(Patient).filter_by(
            first_name=patient_data.first_name,
            last_name=patient_data.last_name
        ))
        patient = result.scalars().first()
        
        if not patient:
            # Add patient to database
            patient = Patient(
                first_name=patient_data.first_name,
                last_name=patient_data.last_name,
                age=patient_data.age,
                bmi=patient_data.bmi,
                chronic_pain=patient_data.chronic_pain,
                recent_surgery=patient_data.recent_surgery
            )
            db.add(patient)
            await db.commit()
            await db.refresh(patient)
            
        # If patient exists and some of the data has changed, update the patient data
        elif patient.age != patient_data.age or patient.bmi != patient_data.bmi or patient.chronic_pain != patient_data.chronic_pain or patient.recent_surgery != patient_data.recent_surgery:
            patient.age = patient_data.age
            patient.bmi = patient_data.bmi
            patient.chronic_pain = patient_data.chronic_pain
            patient.recent_surgery = patient_data.recent_surgery
            await db.commit()
            await db.refresh(patient)
            
            # The patient data has changed, delete the old cache data
            cache_key = get_recommendations_cache_key(patient.id, patient.first_name, patient.last_name)
            await redis_client.delete(cache_key) # If for some reason the cache_key doen't exist, this will not raise an error
        
        # Generate cache key
        cache_key = get_recommendations_cache_key(patient.id, patient.first_name, patient.last_name)
        cached_recommentations = await redis_client.get(cache_key)
        
        if cached_recommentations:
            logger.info("Returning cached recommendations")
            return {
                "message": "Patient already have recommendations for today (retreived from cache)",
                "recommendations": json.loads(cached_recommentations)
            }
        
        recommendations_text = generate_recommendation(patient_data)
        
        today = date.today()
        existing_recommendations = await db.execute(select(Recommendation).filter(
            Recommendation.patient_id == patient.id,
            Recommendation.timestamp >= datetime(today.year, today.month, today.day),
            Recommendation.timestamp < datetime(today.year, today.month, today.day + 1)
        ))
        
        existing_recommendations = existing_recommendations.scalars().all()
        
        if existing_recommendations:
            # Return patient recommendations if they already exist for that day
            return {
                "message" : "Patient already have recommendations for today",
                "recommendations": [rec.recommendation for rec in existing_recommendations]
            }
        
        # Add recommendation to database if it doesn't exist
        for rec in recommendations_text:
            recommendation = Recommendation(
                patient_id=patient.id,
                recommendation=rec
            )
            db.add(recommendation)
            await db.flush()
            
            data = {
                "patient_id": patient.id,
                "recommendation_id": recommendation.id,
                "recommendation": rec,
                "timestamp": recommendation.timestamp.isoformat()
            }
            await redis_client.publish("recommendation_channel", json.dumps(data))
            
        await db.commit()
        await redis_client.set(cache_key, json.dumps(recommendations_text), ex=86400) # 86400 sec = 24 hours expiration
        
        return {"recommendations": recommendations_text}
    
    except Exception as e:
        logger.error(f"Error evaluating the patient: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    

@app.get("/recommendation/{id}", response_model=RecommendationResponse)
async def get_recommendation_by_id(
    id: str, 
    #db: Session = Depends(get_db)
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    cache_key = get_recommendations_cache_key_by_id(id)
    cached_recommendation_by_id = await redis_client.get(cache_key)
    if cached_recommendation_by_id:
        logger.info("Returning cached recommendation by id")
        return json.loads(cached_recommendation_by_id)
    
    #recommendation_result = db.query(Recommendation).filter(Recommendation.id == id).first()
    recommendation_result = await db.execute(select(Recommendation).filter_by(id=id))
    recommendation_result = recommendation_result.scalars().first()
    if not recommendation_result:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    recommendation_data = {
        "id": recommendation_result.id,
        "patient_id": recommendation_result.patient_id,
        "recommendation": recommendation_result.recommendation,
        "timestamp": recommendation_result.timestamp.isoformat()
    }
    
    await redis_client.set(cache_key, json.dumps(recommendation_data), ex=86400) # 86400 sec = 24 hours expiration
    
    return recommendation_result


#---------------------------------------------
# Debug endpoints
@app.get("/patients", response_model=List[PatientResponse])
async def get_patients_debug(db: AsyncSession = Depends(get_db)):
    #patients = db.query(Patient).all()
    patients = await db.execute(select(Patient))
    return patients.scalars().all()

@app.get("/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations_debug(db: AsyncSession = Depends(get_db)):
    #recommendations = db.query(Recommendation).all()
    recommendations = await db.execute(select(Recommendation))
    return recommendations.scalars().all()
    

