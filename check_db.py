from app.db import test_connection

if __name__ == "__main__":
    print("Connexion PostgreSQL réussie !")
    print(test_connection())