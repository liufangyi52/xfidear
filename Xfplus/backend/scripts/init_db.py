from backend.services.seed_service import initialize_database


def main() -> None:
    initialize_database()
    print("SQLite database initialized.")


if __name__ == "__main__":
    main()
