from backend.app.database.initialization import initialize_database


if __name__ == "__main__":
    initialize_database()
    print("Database tables initialized.")