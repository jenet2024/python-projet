from modulefinder import test

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status, Query, Path
from fastapi import FastAPI , Response
from pydantic import BaseModel, Field , ConfigDict
from fastapi.testclient import TestClient
from typing import List, Optional
from pydantic import validator
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.orm import relationship
from sqlalchemy import Table 
# from testPYA import *

# composants de sqlAlchemy Base de données SQLite en mémoire
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modèle SQLAlchemy
# creer le schema pydantic pour etuiant
class Etudiant(BaseModel):
    __tablename__ = "etudiants"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, min_length=2, max_length=100)
    email = Column(String(200), unique=True, nullable=False)
    note = Column(Float, nullable=True)
    actif = Column(Boolean, default=True)
    cours=relationship("Cours", secondary="inscriptions", back_populates="etudiants")
    
    
    
    class Config:
        orm_mode = True


model_config = ConfigDict(from_attributes=True)
# faire la conversion reéelle
Base.metadata.create_all(bind=engine) 
print("Setup OK — Table 'etudiants' créée en mémoire")

#creer le schema pydantic pour etudiant update
class EtudiantUpdate(BaseModel):
    nom: Optional[str] = Field(None, example="Alice Dupont")
    email: Optional[str] = Field(None, example="alice.dupont@example.com")
    note: Optional[float] = Field(None, example=8.5)
    actif: Optional[bool] = Field(None, example=True)
    
    class Config:
        orm_mode = True
#faire autre conversion reéelle
Base.metadata.create_all(bind=engine)
print("Setup OK — Table 'etudiants' mise à jour pour les champs optionnels")

#class EtudiantOut(Etudiant):
class EtudiantOut(BaseModel):
    id: int
    nom: str
    email: str
    note: Optional[float]
    actif: bool
    model_config = ConfigDict(from_attributes=True)
    
    class Config:
        orm_mode = True
class CoursOut(BaseModel):
    id: int
    nom: str
    credits: int
    description: Optional[str]
    etudiants: List[EtudiantOut] = []
    model_config = ConfigDict(from_attributes=True) 

# configurer model config=configDIct pour permettre la conversion depuis un objet SQLAlchemy
model_config = ConfigDict(from_attributes=True)
        
        
# table d'inscription N:N entre etudiant et cours
inscription = Table(
    "inscriptions",
    Base.metadata,
    Column("etudiant_id", Integer, primary_key=True),
    Column("cours_id", Integer, primary_key=True)
)

# table de cours
class Cours(Base):
    __tablename__ = "cours"
    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String(200), nullable=False)
    credits = Column(Integer, nullable=False)
    etudiants = relationship("Etudiant", secondary="inscriptions", back_populates="cours")
    


class Cours(Base):
    __tablename__ = "cours"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, min_length=2, max_length=100)
    description = Column(String(500), nullable=True)
    etudiants=relationship("Etudiant", secondary="inscriptions", back_populates="cours")

base.metadata.create_all(bind=engine)

class EtudiantCreate(BaseModel):
    nom: str = Field(..., min_length=2)
    email: str = Field(..., min_length=2, max_length=200)

app=FastAPI()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/etudiants/", response_model=EtudiantOut, status_code=status.HTTP_201_CREATED)
def create_etudiant(data: EtudiantCreate, db: Session = Depends(get_db)):
    etudiant = Etudiant(**data.model_dump())
    db.add(etudiant)
    db.commit()
    db.refresh(etudiant)
    return etudiant




#exercice 3 : inscrire un etudiant a u, cours
@app.post("/inscriptions/", status_code=status.HTTP_201_CREATED)
def inscrire_etudiant_cours(etudiant_id: int, cours_id: int, db: Session = Depends(get_db)):
    etudiant = db.query(Etudiant).filter(Etudiant.id == etudiant_id).first()
    cours = db.query(Cours).filter(Cours.id == cours_id).first()
    if not etudiant or not cours:
        raise HTTPException(status_code=404, detail="Etudiant ou Cours non trouvé")
    etudiant.cours.append(cours)
    db.commit()
    return {"message": f"Etudiant {etudiant.nom} inscrit au cours {cours.nom}"}

#recuperer le cours pas id 404 si inexistant
@app.get("/cours/{cours_id}", response_model=CoursOut)
def get_cours(cours_id: int, db: Session = Depends(get_db)):
    cours = db.query(Cours).filter(Cours.id == cours_id).first()
    if not cours:
        raise HTTPException(status_code=404, detail="Cours non trouvé")
    return cours


# verifier que l'etudiant n'est pas inscrit 409 si deja inscrit
@app.post("/inscriptions/", status_code=status.HTTP_201_CREATED)
def inscrire_etudiant_cours(etudiant_id: int, cours_id: int, db: Session = Depends(get_db)):
    etudiant = db.query(Etudiant).filter(Etudiant.id == etudiant_id).first()
    cours = db.query(Cours).filter(Cours.id == cours_id).first()
    if not etudiant or not cours:
        raise HTTPException(status_code=404, detail="Etudiant ou Cours non trouvé")
    if cours in etudiant.cours:
        raise HTTPException(status_code=409, detail="Etudiant déjà inscrit à ce cours")
    etudiant.cours.append(cours)
    db.commit()
    return {"message": f"Etudiant {etudiant.nom} inscrit au cours {cours.nom}"}

#ajouter le cours a etudiant.cours(la relation relationSQLALCHEMY gere la table

# uriliser joinedload pour eviter le N+1 problem
from sqlalchemy.orm import joinedload
@app.get("/cours/{cours_id}", response_model=CoursOut)
def get_cours(cours_id: int, db: Session = Depends(get_db)):
    cours = db.query(Cours).options(joinedload(Cours.etudiants)).filter(Cours.id == cours_id).first()
    if not cours:
        raise HTTPException(status_code=404, detail="Cours non trouvé")
    return cours

