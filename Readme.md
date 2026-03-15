# Tâches du jour 

Reprendre votre fichier main.py du Jour 1
Ajouter les métadonnées de l'app (title, description, contact, license)
Enrichir chaque route avec :
Summary et description détaillée
Descriptions des paramètres (Query, Path)
Exemples de réponses (succès et erreurs)
Tags pour organiser les endpoints
Créer un modèle ErrorResponse pour standardiser les erreurs
Ajouter des exemples dans les modèles Pydantic (Config.json_schema_extra)


## Exercice 1
Ajouter l'authentification JWT à votre API Library du Jour 1.

Fonctionnalités à implémenter
Route de login : POST /auth/login (username + password → JWT)
Protéger les routes :
GET /books : Authentification requise
POST /books : Authentification requise
PUT /books/{id} : Authentification requise
DELETE /books/{id} : Admin uniquement
Route me : GET /auth/me (récupère infos user connecté)
Gestion des rôles : user / admin


## Gestion du cache sur toutes les méthodes que j'ai faite 
gestion du cahe sur toutes les methodes qu ej'ai faite 