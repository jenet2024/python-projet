from unittest import result

from fastapi import FastAPI, HTTPException, status, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from auth import *
import redis
import json
from typing import Optional
from datetime import timedelta

# Connexion Redis (pool de connexions pour performance)
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,  # Décode automatiquement bytes → str
    socket_connect_timeout=5
)

# Tester la connexion
try:
    redis_client.ping()
    print("✅ Redis connecté")
except redis.ConnectionError:
    print("❌ Redis non accessible")

app = FastAPI(
    title="Library API",
    description="API REST pour gérer une bibliothèque de livres et d'auteurs.",
    version="1.0.0",
    contact={
        "name": "Support Technique",
        "email": "support@library-api.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)




# -------------------------------------------------------------------
# MODELES D'ERREUR STANDARDISES
# -------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Type d'erreur technique ou fonctionnelle")
    message: str = Field(..., description="Message lisible par un humain")
    details: Optional[dict] = Field(None, description="Détails supplémentaires sur l'erreur (facultatif)")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "NotFoundError",
                "message": "Book with ID 42 not found",
                "details": {"book_id": 42}
            }
        }

common_error_responses = {
    400: {
        "description": "Paramètres invalides",
        "model": ErrorResponse
    },
    404: {
        "description": "Ressource non trouvée",
        "model": ErrorResponse
    },
    422: {
        "description": "Erreur de validation des données",
        "model": ErrorResponse
    }
}

# -------------------------------------------------------------------
# MODELES BOOKS
# -------------------------------------------------------------------

class Book(BaseModel):
    id: Optional[int] = Field(None, description="ID unique du livre (auto-généré)")
    title: str = Field(..., min_length=3, max_length=200, description="Titre du livre")
    author: str = Field(..., min_length=2, max_length=100, description="Nom de l'auteur (texte libre)")
    year: Optional[int] = Field(None, ge=1000, le=2100, description="Année de publication")
    genre: Optional[str] = Field(None, max_length=50, description="Genre littéraire")
    isbn: Optional[str] = Field(None, max_length=17, description="Code ISBN-13")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "1984",
                "author": "George Orwell",
                "year": 1949,
                "genre": "Science-fiction dystopique",
                "isbn": "978-0451524935"
            }
        }

class PaginatedBooks(BaseModel):
    data: List[Book] = Field(..., description="Liste de livres pour la page courante")
    total: int = Field(..., description="Nombre total de livres disponibles")
    page: int = Field(..., description="Numéro de la page courante (>= 1)")
    pages: int = Field(..., description="Nombre total de pages disponibles")

# -------------------------------------------------------------------
# MODELES AUTHORS
# -------------------------------------------------------------------

class Author(BaseModel):
    id: Optional[int] = Field(None, description="ID unique de l'auteur (auto-généré)")
    name: str = Field(..., min_length=3, max_length=100, description="Nom complet de l'auteur")
    birth_year: Optional[int] = Field(None, ge=1000, le=2100, description="Année de naissance")
    death_year: Optional[int] = Field(None, ge=1000, le=2100, description="Année de décès (si applicable)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "George Orwell",
                "birth_year": 1903,
                "death_year": 1950
            }
        }

class PaginatedAuthors(BaseModel):
    data: List[Author] = Field(..., description="Liste d'auteurs pour la page courante")
    total: int = Field(..., description="Nombre total d'auteurs disponibles")
    page: int = Field(..., description="Numéro de la page courante (>= 1)")
    pages: int = Field(..., description="Nombre total de pages disponibles")

# -------------------------------------------------------------------
# BASES DE DONNEES SIMULEES (EN MEMOIRE)
# -------------------------------------------------------------------

books_db: List[dict] = []
authors_db: List[dict] = []
next_book_id = 1
next_author_id = 1

# -------------------------------------------------------------------
# ROUTE ROOT
# -------------------------------------------------------------------

@app.get(
    "/",
    tags=["Root"],
    summary="Point d'entrée de l'API",
    description="""
## Description
Point d'entrée de l'API Library.  
Retourne un message de bienvenue ainsi que quelques informations de base sur l'API.

## Exemples d'utilisation
- `/` : Vérifier que l'API est en ligne.
"""
)
def read_root():
    return {
        "message": "Bienvenue sur l'API Library",
        "version": "1.0.0",
        "endpoints": {
            "books": "/books",
            "authors": "/authors",
            "docs": "/docs"
        }
    }

# -------------------------------------------------------------------
# ROUTES BOOKS
# -------------------------------------------------------------------

@app.get(
    "/books",
    response_model=PaginatedBooks,
    status_code=status.HTTP_200_OK,
    tags=["Books"],
    summary="Lister les livres (pagination + filtres)",
    description="""
## Description
Retourne une **liste paginée** de livres, avec la possibilité de filtrer par auteur et par plage d'années.

## Paramètres de requête
- **page** *(int, défaut = 1)* : Numéro de page (commence à 1).
- **limit** *(int, défaut = 10, max = 100)* : Nombre d'éléments par page.
- **author** *(str, optionnel)* : Filtrer par nom d'auteur (recherche partielle, insensible à la casse).
- **year_min** *(int, optionnel)* : Filtrer par année de publication minimale.
- **year_max** *(int, optionnel)* : Filtrer par année de publication maximale.

## Exemples d'utilisation
- `/books?page=1&limit=20` : Première page, 20 livres.
- `/books?author=Orwell` : Tous les livres dont l'auteur contient 'Orwell'.
- `/books?year_min=1900&year_max=2000` : Livres publiés entre 1900 et 2000.
- `/books?author=Orwell&year_min=1940` : Livres d'Orwell publiés après 1940.

## Réponse 200 - Succès
```json
{
  "data": [
    {
      "id": 1,
      "title": "1984",
      "author": "George Orwell",
      "year": 1949,
      "genre": "Science-fiction dystopique",
      "isbn": "978-0451524935"
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
"""
)
def list_books(
    page: int = Query(1, ge=1, description="Numéro de page (commence à 1)"),
    limit: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page")
):
    # Filtrage et pagination simulés (à remplacer par une vraie logique de base de données)
    filtered_books = books_db  # Appliquer les filtres ici si nécessaire
    total = len(filtered_books)
    start = (page - 1) * limit
    end = start + limit
    paginated_books = filtered_books[start:end]
    return PaginatedBooks(data=paginated_books, total=total, page=page, pages=(total + limit - 1) // limit)


# Les autres routes (GET /books/{id}, POST /books, PUT /books/{id}, DELETE /books/{id}, etc.) seraient définies ici de manière similaire, en utilisant les modèles et les réponses d'erreur standardisés.
def get_book(book_id: int = Path(..., ge=1, description="ID du livre à récupérer")):
    for book in books_db:
        if book["id"] == book_id:
            return book
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Book with ID {book_id} not found",
        details={"book_id": book_id}
    ).dict())
    
def create_book(book: Book):
    global next_book_id
    new_book = book.dict()
    new_book["id"] = next_book_id
    books_db.append(new_book)
    next_book_id += 1
    return new_book

def update_book(book_id: int, book: Book):
    for idx, existing_book in enumerate(books_db):
        if existing_book["id"] == book_id:
            updated_book = book.dict()
            updated_book["id"] = book_id
            books_db[idx] = updated_book
            return updated_book
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Book with ID {book_id} not found",
        details={"book_id": book_id}
    ).dict())

def delete_book(book_id: int):
    for idx, existing_book in enumerate(books_db):
        if existing_book["id"] == book_id:
            del books_db[idx]
            return {"message": f"Book with ID {book_id} deleted successfully"}
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Book with ID {book_id} not found",
        details={"book_id": book_id}
    ).dict())

def list_authors(
    page: int = Query(1, ge=1, description="Numéro de page (commence à 1)"),
    limit: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page")
):
    # Filtrage et pagination simulés (à remplacer par une vraie logique de base de données)
    total = len(authors_db)
    start = (page - 1) * limit
    end = start + limit
    paginated_authors = authors_db[start:end]
    return PaginatedAuthors(data=paginated_authors, total=total, page=page, pages=(total + limit - 1) // limit)

def get_author(author_id: int = Path(..., ge=1, description="ID de l'auteur à récupérer")):
    for author in authors_db:
        if author["id"] == author_id:
            return author
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Author with ID {author_id} not found",
        details={"author_id": author_id}
    ).dict())

def create_author(author: Author):
    global next_author_id
    new_author = author.dict()
    new_author["id"] = next_author_id
    authors_db.append(new_author)
    next_author_id += 1
    return new_author
def update_author(author_id: int, author: Author):
    for idx, existing_author in enumerate(authors_db):
        if existing_author["id"] == author_id:
            updated_author = author.dict()
            updated_author["id"] = author_id
            authors_db[idx] = updated_author
            return updated_author
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Author with ID {author_id} not found",
        details={"author_id": author_id}
    ).dict())
def delete_author(author_id: int):
    for idx, existing_author in enumerate(authors_db):
        if existing_author["id"] == author_id:
            del authors_db[idx]
            return {"message": f"Author with ID {author_id} deleted successfully"}
    raise HTTPException(status_code=404, detail=ErrorResponse(
        error="NotFoundError",
        message=f"Author with ID {author_id} not found",
        details={"author_id": author_id}
    ).dict())



# crud books
@app.get("/books/{book_id}", response_model=Book, status_code=status.HTTP_200_OK
    , tags=["Books"], summary="Récupérer un livre par ID", description="""
## Description
Retourne les détails d'un livre spécifique en fonction de son ID.
## Paramètres de chemin
- **book_id** *(int)* : ID du livre à récupérer (doit être un entier positif).
## Exemples d'utilisation       
- `/books/1` : Récupérer le livre avec l'ID 1.
## Réponse 200 - Succès 
```json
{
  "id": 1,
  "title": "1984",
  "author": "George Orwell",
  "year": 1949,
  "genre": "Science-fiction dystopique",
  "isbn": "978-0451524935"
}
```
## Réponse 404 - Livre non trouvé
```json
{
  "error": "NotFoundError",
  "message": "Book with ID 42 not found",
  "details": {"book_id": 42}
}
```
""")
async def get_book(book_id: int):
    cache_key = f"book:{book_id}"
    
    # 1. Vérifier le cache
    cached = redis_client.get(cache_key)
    if cached:
        print(f"✅ CACHE HIT - Book {book_id}")
        return json.loads(cached)
    
    # 2. Cache MISS : requête DB
    print(f"❌ CACHE MISS - Query DB for book {book_id}")
    book = None
    for b in books_db:
        if b["id"] == book_id:
            book = b
            break
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # 3. Mettre en cache (expire dans 5 minutes)
    redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(book)
    )
    
    return book

def read_book(book_id: int = Path(..., ge=1, description="ID du livre à récupérer")):
    return get_book(book_id)

@app.post("/books", response_model=Book, status_code=status.HTTP_201_CREATED
    , tags=["Books"], summary="Créer un nouveau livre", description="""
## Description  
Crée un nouveau livre dans la bibliothèque en fournissant les détails nécessaires.
## Corps de la requête
- **title** *(str)* : Titre du livre (obligatoire, 3-200 caractères).
- **author** *(str)* : Nom de l'auteur (obligatoire, 2
-100 caractères).
- **year** *(int)* : Année de publication (optionnelle, entre 1000 et 2100).
- **genre** *(str)* : Genre littéraire (optionnelle, max 50 caractères).
- **isbn** *(str)* : Code ISBN-13 (optionnelle, max 17 caractères).
## Exemples d'utilisation
- POST `/books` avec le corps :
```json
{
  "title": "1984",
  "author": "George Orwell",
  "year": 1949,
  "genre": "Science-fiction dystopique",
  "isbn": "978-0451524935"
}
```
## Réponse 201 - Livre créé
```json
{
  "id": 1,
  "title": "1984",
  "author": "George Orwell",
  "year": 1949,
  "genre": "Science-fiction dystopique",
  "isbn": "978-0451524935"
}
```
## Réponse 422 - Erreur de validation
```json
{
  "error": "ValidationError",
  "message": "Validation failed for the request body",
  "details": {
    "title": ["field required"],
    "author": ["field required"]
  }
}
```
""")
def create_new_book(book: Book):
    return create_book(book)

@app.put("/books/{book_id}", response_model=Book, status_code=status.HTTP_200_OK
    , tags=["Books"], summary="Mettre à jour un livre existant", description="""
## Description
Met à jour les détails d'un livre existant en fonction de son ID.
## Paramètres de chemin
- **book_id** *(int)* : ID du livre à mettre à jour (doit
être un entier positif).
## Corps de la requête  
- **title** *(str)* : Titre du livre (obligatoire, 3-200 caractères).
- **author** *(str)* : Nom de l'auteur (obligatoire, 2
-100 caractères).
- **year** *(int)* : Année de publication (optionnelle, entre 1000 et 2100).
- **genre** *(str)* : Genre littéraire (optionnelle, max 50 caractères).
- **isbn** *(str)* : Code ISBN-13 (optionnelle, max 17 caractères).
## Exemples d'utilisation
- PUT `/books/1` avec le corps :
```json
{
  "title": "1984 (édition révisée)",
  "author": "George Orwell",
  "year": 1950,
  "genre": "Science-fiction dystopique",
  "isbn": "978-0451524935"
}
```
## Réponse 200 - Livre mis à jour
```json
{
  "id": 1,
  "title": "1984 (édition révisée)",
  "author": "George Orwell",
  "year": 1950,
  "genre": "Science-fiction dystopique",
  "isbn": "978-0451524935"
}
```
## Réponse 404 - Livre non trouvé
```json
{
  "error": "NotFoundError",
  "message": "Book with ID 42 not found",
  "details": {"book_id": 42}
}
``` 
## Réponse 422 - Erreur de validation
```json
{
  "error": "ValidationError",
  "message": "Validation failed for the request body",
  "details": {
    "title": ["field required"],
    "author": ["field required"]
  }
}
```
""")
async def update_book(book_id: int, book_update: Book):
    # 1. Mettre à jour en DB
    for i, book in enumerate(books_db):
        if book["id"] == book_id:
            book_update.id = book_id
            books_db[i] = book_update.dict()
            
            # 2. INVALIDER LE CACHE
            cache_key = f"book:{book_id}"
            redis_client.delete(cache_key)
            print(f"🗑️ Cache invalidé pour book {book_id}")
            
            return book_update
    
    raise HTTPException(status_code=404, detail="Book not found")

@app.delete("/books/{book_id}", status_code=204)
async def delete_book(book_id: int):
    for i, book in enumerate(books_db):
        if book["id"] == book_id:
            books_db.pop(i)
            
            # Invalider le cache
            cache_key = f"book:{book_id}"
            redis_client.delete(cache_key)
            
            return
    
    raise HTTPException(status_code=404, detail="Book not found")

def update_existing_book(book_id: int, book: Book):
    return update_book(book_id, book)

@app.delete("/books/{book_id}", status_code=status.HTTP_200_OK
    , tags=["Books"], summary="Supprimer un livre", description="""
## Description
Supprime un livre de la bibliothèque en fonction de son ID. 
## Paramètres de chemin
- **book_id** *(int)* : ID du livre à supprimer (doit être un entier positif).
## Exemples d'utilisation       
- DELETE `/books/1` : Supprimer le livre avec l'ID 1.
## Réponse 200 - Livre supprimé
```json
{
  "message": "Book with ID 1 deleted successfully"
}
```
## Réponse 404 - Livre non trouvé
```json
{
  "error": "NotFoundError",
  "message": "Book with ID 42 not found",
  "details": {"book_id": 42}
}
```
""")
def delete_existing_book(book_id: int):
    return delete_book(book_id)

# crud authors
@app.get("/authors", response_model=PaginatedAuthors, status_code=status.HTTP_200_OK
    , tags=["Authors"], summary="Lister les auteurs (pagination)", description="""  
## Description
Retourne une **liste paginée** d'auteurs disponibles dans la bibliothèque.
## Paramètres de requête
- **page** *(int, défaut = 1)* : Numéro de page (commence à 1).
- **limit** *(int, défaut = 10, max = 100)* : Nombre d'éléments par page.
## Exemples d'utilisation
- `/authors?page=1&limit=20` : Première page, 20 auteurs.   
## Réponse 200 - Succès
```json
{
  "data": [
    {
      "id": 1,
      "name": "George Orwell",
      "birth_year": 1903,
      "death_year": 1950
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```
""")
async def get_author_by_id(author_id: int):
    cache_key = f"author:{author_id}"
    
    # 1. Vérifier le cache
    cached = redis_client.get(cache_key)
    if cached:
        print(f"✅ CACHE HIT - Author {author_id}")
        return json.loads(cached)
    
    # 2. Cache MISS : requête DB
    print(f"❌ CACHE MISS - Query DB for author {author_id}")
    author = None
    for a in authors_db:
        if a["id"] == author_id:
            author = a
            break
    
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    # 3. Mettre en cache (expire dans 5 minutes)
    redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(author)
    )
    # gerer le temps de mises en cache + invalidation à la modification (PUT/DELETE des auteurs)
    redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(author)
    )
    
    return author
    
   
def list_all_authors(
    page: int = Query(1, ge=1, description="Numéro de page (commence à 1)"),
    limit: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page")
):
    return list_authors(page, limit)
















#Ajouter l'authentification JWT à login .


#Route de login : POST /auth/login (username + password → JWT)
@app.post("/auth/login", response_model=Token, tags=["Auth"], summary="Se connecter", description="""
## Description
Permet à un utilisateur de se connecter en fournissant son nom d'utilisateur et son mot de passe.
## Corps de la requête
- **username** *(str)* : Nom d'utilisateur (doit exister dans la base de données).
- **password** *(str)* : Mot de passe (doit correspondre au hash stocké).
## Réponse 200 - Connexion réussie
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3MDk4MjQwMDB9.7v8f8F7gH8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjoxNzEwNDI4ODAwfQ.8w9x0y1z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8",
  "token_type": "bearer"
}
```
## Réponse 401 - Échec de l'authentification
```json
{
  "error": "Unauthorized",
  "message": "Incorrect username or password"
}
```
""")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=refresh_token_expires,
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

# Route GET auth/me : Récupérer les infos de l'utilisateur actuel (JWT → user info)
@app.get("/auth/me", response_model=User, tags=["Auth"], summary="Récupérer les infos de l'utilisateur actuel", description="""
## Description
Permet à un utilisateur authentifié de récupérer ses propres informations à partir du token JWT fourni dans l'en-tête Authorization.
## En-têtes de la requête   
- **Authorization** *(str)* : Doit être au format `Bearer <token>`, où `<token>` est un JWT valide obtenu lors de la connexion.
## Réponse 200 - Succès
```json
{
  "id": 1,
  "username": "alice",
  "full_name": "Alice Dupont",
  "email": "alice@example.com"
}
```
## Réponse 401 - Token invalide ou expiré
```json
{
  "error": "Unauthorized",
  "message": "Could not validate credentials"
}
```
""")
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user





# Connexion Redis (pool de connexions pour performance)
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,  # Décode automatiquement bytes → str
    socket_connect_timeout=5
)

# Tester la connexion
try:
    redis_client.ping()
    print("✅ Redis connecté")
except redis.ConnectionError:
    print("❌ Redis non accessible")

# ========== PATTERN CACHE-ASIDE ==========


# ========== INVALIDATION DU CACHE (lors d'une modification) ==========


@app.delete("/books/{book_id}", status_code=204)
async def delete_book(book_id: int):
    for i, book in enumerate(books_db):
        if book["id"] == book_id:
            books_db.pop(i)
            
            # Invalider le cache
            cache_key = f"book:{book_id}"
            redis_client.delete(cache_key)
            
            return
    
    raise HTTPException(status_code=404, detail="Book not found")


# gestion du cache pour les listes (ex: GET /books avec filtres)
@app.get("/books", response_model=PaginatedBooks)
async def list_books(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    title: Optional[str] = Query(None),
    author: Optional[str] = Query(None)
):
    # Clé de cache basée sur les paramètres de requête
    cache_key = f"books:page={page}:limit={limit}:title={title}:author={author}"
    
    # Vérifier le cache
    cached = redis_client.get(cache_key)
    if cached:
        print(f"✅ CACHE HIT - List books with filters")
        return json.loads(cached)
    
    print(f"❌ CACHE MISS - Query DB for list books with filters")
    # Simuler le filtrage et la pagination (à remplacer par une vraie logique DB)
    filtered_books = books_db
    if title:
        filtered_books = [b for b in filtered_books if title.lower() in b["title"].lower()]
    if author:
        filtered_books = [b for b in filtered_books if author.lower() in b["author"].lower()]
    
    total = len(filtered_books)
    start = (page - 1) * limit
    end = start + limit
    paginated_books = filtered_books[start:end]
    
    result = PaginatedBooks(data=paginated_books, total=total, page=page, pages=(total + limit - 1) // limit)
    
    # Mettre en cache le résultat (expire dans 5 minutes)
    redis_client.setex(
        cache_key,
        timedelta(minutes=1),
        result.json()
    )
    # gerer le temps de mises en cache + invalidation à la modification (PUT/DELETE des auteurs)
    redis_client.setex(
        cache_key,
        timedelta(minutes=4),
        json.dumps(author)
    )
    return result


# SYSTEME DE cache pour les get_authors (pagination + filtres) + invalidation à la modification (PUT/DELETE des auteurs)
@app.get("/authors/{author_id}", response_model=Author, status_code=status.HTTP_200_OK
    , tags=["Authors"], summary="Récupérer un auteur par ID", description="""
## Description  
Retourne les détails d'un auteur spécifique en fonction de son ID, avec mise en cache pour
améliorer les performances.
## Paramètres de chemin
- **author_id** *(int)* : ID de l'auteur à récupérer (doit être un entier positif).
## Exemples d'utilisation
- `/authors/1` : Récupérer l'auteur avec l'ID 1.
## Réponse 200 - Succès
```json
{
  "id": 1,
  "name": "George Orwell",
  "birth_year": 1903,
  "death_year": 1950
}
```
## Réponse 404 - Auteur non trouvé
```json
{
  "error": "NotFoundError",
  "message": "Author with ID 42 not found",
  "details": {"author_id": 42}
}
```
""")
async def get_author_by_id(author_id: int):
    cache_key = f"author:{author_id}"
    
    # 1. Vérifier le cache
    cached = redis_client.get(cache_key)
    if cached:
        print(f"✅ CACHE HIT - Author {author_id}")
        return json.loads(cached)
    
    # 2. Cache MISS : requête DB
    print(f"❌ CACHE MISS - Query DB for author {author_id}")
    author = None
    for a in authors_db:
        if a["id"] == author_id:
            author = a
            break
    
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    # 3. Mettre en cache (expire dans 5 minutes)
    redis_client.setex(
        cache_key,
        timedelta(minutes=1),
        json.dumps(author)
    )
    # gerer le temps de mises en cache + invalidation à la modification (PUT/DELETE des auteurs)
    redis_client.setex(
        cache_key,
        timedelta(minutes=6),
        json.dumps(author)
    )
    
    return author



