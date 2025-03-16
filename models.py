from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
#from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base
import uuid
import datetime

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    bmi = Column(Float, nullable=False)
    chronic_pain = Column(Boolean, nullable=False)
    recent_surgery = Column(Boolean, nullable=False)

    # Relationship to recommendations (one-to-many). A patient can have multiple recommendations
    recommendations = relationship("Recommendation", back_populates="patient", cascade="all, delete-orphan")

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())) # Generate a random UUID when inserting a new recommendation
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow) # Generate the current timestamp when inserting a new recommendation

    # Relationship to patient (many-to-one). Many recommendation can belong to one patient
    patient = relationship("Patient", back_populates="recommendations")
    

