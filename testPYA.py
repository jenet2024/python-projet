
# %%
print("Notebook OK")

# %% ===================== IMPORTS =====================
from fastapi import FastAPI, HTTPException, status, Query, Path
from fastapi import FastAPI , Response
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, validator, ValidationError
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# Base SQLAlchemy
engine = create_engine("sqlite:///:memory:", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
# %% ===================== MODELES COURS =====================

class CoursCreate(BaseModel):
    titre: str = Field(..., min_length=2)
    niveau: str = Field(..., pattern="^(debutant|intermediaire|avance)$")
    duree: int = Field(..., ge=1)
    prix: float = Field(0.0, ge=0)
    tags: Optional[List[str]] = Field(default_factory=list, max_length=5)

    @validator("titre")
    def strip_titre(cls, v):
        return v.strip()

    @validator("titre")
    def capitalize_titre(cls, v):
        return v.title()


class CoursResponse(CoursCreate):
    id: int
    class Config:
        orm_mode = True


# %% ===================== TEST COURS =====================

def test_cours_create():
    print("\n=== TEST COURS ===")

    cours = CoursCreate(
        titre="  python avance  ",
        niveau="avance",
        duree=21,
        prix=499.0
    )

    assert cours.titre == "Python Avance"
    assert cours.niveau == "avance"
    assert cours.prix == 499.0
    assert cours.tags == []
    print("✅ Test 1 OK — Création valide avec capitalisation")

    # Niveau invalide
    try:
        CoursCreate(titre="Cours Invalide", niveau="expert", duree=10, prix=199.0)
        assert False
    except ValidationError:
        print("✅ Test 2 OK — Niveau invalide rejeté")

    # Prix négatif
    try:
        CoursCreate(titre="Cours Invalide", niveau="debutant", duree=10, prix=-50.0)
        assert False
    except ValidationError:
        print("✅ Test 3 OK — Prix négatif rejeté")

    # Titre trop court
    try:
        CoursCreate(titre="A", niveau="debutant", duree=10, prix=199.0)
        assert False
    except ValidationError:
        print("✅ Test 4 OK — Titre trop court rejeté")

    # Trop de tags
    try:
        CoursCreate(
            titre="test valide",
            niveau="debutant",
            duree=10,
            tags=["a", "b", "c", "d", "e", "f"]
        )
        assert False
    except ValidationError:
        print("✅ Test 5 OK — Trop de tags rejeté")

    print("🎉 Tous les tests CoursCreate sont passés !")

# %% ===================== EXECUTION TEST COURS =====================

test_cours_create()

# %% ===================== MODELES ETUDIANT =====================

class Etudiant(Base):
    __tablename__ = "etudiants"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    note = Column(Float, nullable=True)
    actif = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)


class EtudiantCreate(BaseModel):
    nom: str = Field(..., min_length=2)
    email: str
    note: Optional[float] = None
    actif: bool = True


class EtudiantUpdate(BaseModel):
    nom: Optional[str] = None
    email: Optional[str] = None
    note: Optional[float] = None
    actif: Optional[bool] = None


class EtudiantOut(BaseModel):
    id: int
    nom: str
    email: str
    note: Optional[float]
    actif: bool

    class Config:
        orm_mode = True

# %% ===================== TEST ETUDIANT =====================

def test_etudiant_create():
    print("\n=== TEST ETUDIANT ===")

    e = EtudiantCreate(nom="Alice", email="alice@univ.fr")
    assert e.nom == "Alice"
    assert e.email == "alice@univ.fr"
    print("✅ EtudiantCreate OK")

    # min_length
    try:
        EtudiantCreate(nom="A", email="a@b.fr")
        assert False
    except Exception:
        print("✅ Validation min_length OK")

    # EtudiantUpdate vide
    u = EtudiantUpdate()
    assert u.nom is None
    assert u.email is None
    assert u.note is None
    assert u.actif is None
    print("✅ EtudiantUpdate vide OK")

    # EtudiantUpdate partiel
    u2 = EtudiantUpdate(note=15.5)
    assert u2.note == 15.5
    print("✅ EtudiantUpdate partiel OK")

    # ORM → Pydantic
    db = SessionLocal()
    db_etudiant = Etudiant(nom="Bob", email="bob@univ.fr")
    db.add(db_etudiant)
    db.commit()
    db.refresh(db_etudiant)

    out = EtudiantOut.model_validate(db_etudiant)
    assert out.nom == "Bob"
    assert out.email == "bob@univ.fr"
    assert out.id is not None
    assert out.actif is True
    db.close()
    print("✅ EtudiantOut from_attributes OK")

    print("🎉 Tous les tests Etudiant sont passés !")


# %% ===================== EXECUTION TEST ETUDIANT =====================

test_etudiant_create()

# %%
