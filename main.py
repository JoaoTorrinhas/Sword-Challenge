from fastapi import FastAPI, Depends, HTTPException, Query 
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from models import Patient, Recommendation
from connection_db import get_db, create_all_tables
from typing import List
import redis.asyncio as redis 
import json
import jwt
import os
import logging
import asyncio
import datetime

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
    
# Request and Response models for json data
class PatientData(BaseModel):
    age: int
    bmi: float
    chronic_pain: bool
    recent_surgery: bool

class PatientResponse(BaseModel):
    id: int
    age: int
    bmi: float
    chronic_pain: bool
    recent_surgery: bool    
    
class RecommendationResponse(BaseModel):
    id: str
    patient_id: int
    recommendation: str
    timestamp: datetime.datetime

# Create all table on startup
@app.on_event("startup")
async def on_startup():
    await create_all_tables()


def generate_recommendation(patient_data: PatientData) -> str:
    if patient_data.age > 65 and patient_data.chronic_pain:
        return "Physical Therapy"
    elif patient_data.bmi > 30:
        return "Weight Management Program"
    elif patient_data.recent_surgery:
        return "Post-Op Rehabilitation Plan"
    else:
        return "General Health Checkup"


@app.post("/evaluate")
async def evaluate_pacient(
    patient_data: PatientData,
    #db: Session = Depends(get_db)
    db: AsyncSession = Depends(get_db)
):  
    try:
        # Check if patient already exists with same characteristics
        result = await db.execute(select(Patient).filter_by(
            age=patient_data.age, 
            bmi=patient_data.bmi, 
            chronic_pain=patient_data.chronic_pain, 
            recent_surgery=patient_data.recent_surgery
        ))
        patient = result.scalars().first()
        
        if not patient:
            # add patient to database
            patient = Patient(
                age=patient_data.age,
                bmi=patient_data.bmi,
                chronic_pain=patient_data.chronic_pain,
                recent_surgery=patient_data.recent_surgery
            )
            db.add(patient)
            await db.commit()
            await db.refresh(patient)    
        
        recommendation_text = generate_recommendation(patient_data)
        
        # Add recommendation to database
        recommendation = Recommendation(
            patient_id=patient.id,
            recommendation=recommendation_text
        )
        
        db.add(recommendation)
        await db.commit()
        await db.refresh(recommendation)
        
        return {"recomendation": recommendation.recommendation}
    
    except Exception as e:
        logger.error(f"Error evaluating the patient: {e}")
        return HTTPException(status_code=500, detail="Internal Server Error")
    

@app.get("/recommendation/{id}", response_model=RecommendationResponse)
async def get_recommendation(
    id: str, 
    #db: Session = Depends(get_db)
    db: AsyncSession = Depends(get_db)
):
    #recommendation_result = db.query(Recommendation).filter(Recommendation.id == id).first()
    recommendation_result = await db.execute(select(Recommendation).filter_by(id=id))
    recommendation_result = recommendation_result.scalars().first()
    if not recommendation_result:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
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
    

