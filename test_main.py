from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ========== TESTS DE BASE ==========
def test_read_root():
    """Tester la route racine"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

# ========== TESTS CRUD ==========
def test_create_book():
    """Tester la création d'un livre"""
    book_data = {
        "title": "Test Book",
        "author": "Test Author",
        "year": 2024
    }
    response = client.post("/books", json=book_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Book"
    assert "id" in data

def test_get_books():
    """Tester la liste des livres"""
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data

def test_get_book_by_id():
    """Tester la récupération d'un livre par ID"""
    # Créer un livre d'abord
    book = client.post("/books", json={"title": "Book 1", "author": "Author 1"}).json()
    book_id = book["id"]
    
    # Récupérer le livre
    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["id"] == book_id

def test_get_nonexistent_book():
    """Tester 404 pour livre inexistant"""
    response = client.get("/books/999999")
    assert response.status_code == 404
    assert "error" in response.json()

def test_update_book():
    """Tester la mise à jour d'un livre"""
    # Créer
    book = client.post("/books", json={"title": "Old Title", "author": "Author"}).json()
    book_id = book["id"]
    
    # Mettre à jour
    updated = {"title": "New Title", "author": "Author", "year": 2024}
    response = client.put(f"/books/{book_id}", json=updated)
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"

def test_delete_book():
    """Tester la suppression d'un livre"""
    # Créer
    book = client.post("/books", json={"title": "To Delete", "author": "Author"}).json()
    book_id = book["id"]
    
    # Supprimer
    response = client.delete(f"/books/{book_id}")
    assert response.status_code == 204
    
    # Vérifier que le livre n'existe plus
    get_response = client.get(f"/books/{book_id}")
    assert get_response.status_code == 404

# ========== TESTS DE VALIDATION ==========
def test_create_book_invalid_data():
    """Tester la validation Pydantic"""
    # Titre trop court (min 3 caractères)
    response = client.post("/books", json={"title": "AB", "author": "Author"})
    assert response.status_code == 422  # Unprocessable Entity
    
    # Auteur manquant
    response = client.post("/books", json={"title": "Valid Title"})
    assert response.status_code == 422

# ========== TESTS DE PAGINATION ==========
def test_pagination():
    """Tester la pagination"""
    # Créer 50 livres
    for i in range(50):
        client.post("/books", json={"title": f"Book {i}", "author": "Author"})
    
    # Page 1 (20 livres)
    response = client.get("/books?page=1&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 20
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["total"] >= 50
    
    # Page 2
    response = client.get("/books?page=2&limit=20")
    assert len(response.json()["data"]) == 20

# ========== TESTS DE FILTRAGE ==========
def test_filter_by_author():
    """Tester le filtrage par auteur"""
    # Créer des livres
    client.post("/books", json={"title": "Book 1", "author": "Orwell"})
    client.post("/books", json={"title": "Book 2", "author": "Hemingway"})
    
    # Filtrer
    response = client.get("/books?author=Orwell")
    assert response.status_code == 200
    books = response.json()["data"]
    assert all("Orwell" in b["author"] for b in books)

# ========== TESTS D'AUTHENTIFICATION ==========
def test_access_protected_route_without_token():
    """Tester 401 sans token"""
    response = client.get("/books")
    assert response.status_code == 401

def test_login_and_access_protected_route():
    """Tester le flow complet d'authentification"""
    # Login
    login_response = client.post(
        "/auth/login",
        data={"username": "alice", "password": "secret"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Accéder à une route protégée avec le token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/books", headers=headers)
    assert response.status_code == 200

def test_admin_only_route():
    """Tester qu'un user normal ne peut pas accéder aux routes admin"""
    # Login user normal (bob)
    login_response = client.post(
        "/auth/login",
        data={"username": "bob", "password": "secret"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Essayer de supprimer (admin only)
    response = client.delete("/books/1", headers=headers)
    assert response.status_code == 403  # Forbidden