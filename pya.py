# creer une application FastPI
# avec deux endpoints GET/ qui retoune message
#Get :etudiants /count qui retourne le count 5
# utiliser Test Client pour tester les endpoints

from modulefinder import test

import uvicorn
from fastapi import FastAPI, HTTPException, status, Query, Path
from fastapi import FastAPI , Response
from pydantic import BaseModel, Field
from fastapi.testclient import TestClient
from typing import List, Optional
from pydantic import validator
from testPYA import *


app = FastAPI()
client = TestClient(app)

@app.get("/etudiants")
def get_etudiants():
    return {"message": "Liste des étudiants"}

@app.get("/count")
def get_count():
    return {"count": 5}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
#test de  navigation
def test_get_etudiants():
    response = client.get("/etudiants")
    assert response.status_code == 200 ,f"Attendu 200 mais obtenu {response.status_code}"
    assert response.json()["message"] == "Bienvenue sur L'API Formation"
    
    response = client.get("/etudiants/count")
    assert response.status_code == 200 ,f"Attendu 200 mais obtenu {response.status_code}"
    assert "count" in response.json(), "La clé 'count' est absente de la réponse"
    assert response.json()["count"] == 5, f"Attendu 5 mais obtenu {response.json()['count']}"
    
    print("✅ TP1 Tous les tests sont passés avec succès !")

#-------------------------------------
# TP2 Routes et parametres
#------------------------------------- 

DB_COURS = [
    {"id": 1, "titre": "Python Fondamentaux", "niveau": "debutant", "duree": 35, "prix": 299.0},
    {"id": 2, "titre": "FastAPI Avancé", "niveau": "avance", "duree": 21, "prix": 499.0},
    {"id": 3, "titre": "Data Science", "niveau": "intermediaire", "duree": 42, "prix": 599.0},
    {"id": 4, "titre": "SQL pour tous", "niveau": "debutant", "duree": 14, "prix": 199.0},
]
    
DB_ETUDIANTS = {
    1: {"nom": "Alice", "cours_ids": [1, 3]},
    2: {"nom": "Bob", "cours_ids": [2]},
    3: {"nom": "Charlie", "cours_ids": [1, 2, 4]},
}


class CoursCreate(BaseModel):
    titre: str = Field(..., example="Python pour les débutants")
    niveau: str = Field(..., example="debutant")
    duree: int = Field(..., example=30)
    prix: float = Field(..., example=299.0)
    tags: Optional[List[str]] = Field(None, example=["python", "programmation", "débutant"])
    
    # ajout de field validator qui supprime les espaces en debut et fin 
    @validator("titre")
    def strip_titre(cls, v):
        return v.strip()
    # ajout de fielvalidator qui capitalise chaque mot du titre
    @validator("titre")
    def capitalize_titre(cls, v):
        return v.title()
    
class CoursResponse(CoursCreate):
    id: int
    class Config:
        orm_mode = True





# creation d'un endpoint qui liste les cours avec
#niveau(optionnel):filtrer par niveau
#prix_max(optionnel, defaut 9999):filtrer par prix max
#skip(defaut0) et limit(defaut10):pagination

@app.get("/cours/")
async def get_cours(niveau: str = None, prix_max    : float = 999    , skip: int = 0, limit: int = 10):
    cours = DB_COURS
    
    if niveau:
        cours = [c for c in cours if c["niveau"] == niveau]
    
    if prix_max is not None:
        cours = [c for c in cours if c["prix"] <= prix_max]
    
    cours = cours[skip:skip + limit]
    
    return cours

#retouner 400 si le cours n'existe pas 
@app.get("/cours/{cours_id}")
async def get_cours_by_id(cours_id: int):
    cours = next((c for c in DB_COURS if c["id"] == cours_id), None)
    if not cours:
        raise HTTPException(status_code=400, detail="Cours non trouvé")
    return cours


#-------------------------------------------
# tp3 : MODELE COURS CREATE et COURS RESPONSE
#---------------------------------------------------

class CoursCreate(BaseModel):
    titre: str = Field(..., example="Python pour les débutants")
    niveau: str = Field(..., example="debutant")
    duree: int = Field(..., example=30)
    prix: float = Field(..., example=299.0)
    tags: Optional[List[str]] = Field(None, example=["python", "programmation", "débutant"])
    
    # ajout de field validator qui supprime les espaces en debut et fin 
    @validator("titre")
    def strip_titre(cls, v):
        return v.strip()
    # ajout de fielvalidator qui capitalise chaque mot du titre
    @validator("titre")
    def capitalize_titre(cls, v):
        return v.title()
    
class CoursResponse(CoursCreate):
    id: int
    class Config:
        orm_mode = True

# rajouter la methode post pour creer un cours et la methode get pour recuperer un cours par id
app.post("/cours/", response_model=CoursResponse, status_code=201)
async def create_cours(cours: CoursCreate):
    new_cours = CoursResponse(id=123, **cours.dict())
    return new_cours


# reciperer un cours par id en fonction des cours crées
@app.get("/cours/{cours_id}", response_model=CoursResponse)
async def get_cours_by_id(cours_id: int):
    if cours_id != 123:
        raise HTTPException(status_code=404, detail="Cours non trouvé")
    return CoursResponse(
        id=123,
        titre="Machine Learning",
        niveau="intermediaire",
        duree=42,
        prix=599.0,
        tags=["ML", "Python", "Data"]
    )





# ----------------------------------------------
#TP 4 CRUD

#creer un endpoint post qui retourne 201


# creer un objet courscreate pour genrerer un id auto-incrementé global counter 
global_id = 0
def generate_id():
    global global_id
    global_id += 1
    return global_id


#mettre le cours create dans la methode post pour creer un cours avec un id auto-incrementé
@app.post("/cours/", response_model=CoursResponse, status_code=201)
async def create_cours(cours: CoursCreate):
    new_cours = CoursResponse(id=generate_id(), **cours.dict())
    return new_cours

#delete cours par id
@app.delete("/cours/{cours_id}", response_model=dict)
async def delete_cours(cours_id: int):
    if cours_id != 123:
        raise HTTPException(status_code=404, detail="Cours non trouvé")
    return {"message": "Cours supprimé avec succès"}

#retouner le code 204 si la ressource n'existe plus
@app.delete("/cours/{cours_id}", status_code=204)
async def delete_cours(cours_id: int):
    if cours_id != 123:
        raise HTTPException(status_code=404, detail="Cours non trouvé")
    return Response(status_code=204)


