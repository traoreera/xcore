# Module Documentation: database/

The `database/` module is responsible for setting up and managing the database connection within the `xcore` framework. It uses SQLAlchemy as the Object-Relational Mapper (ORM) and provides a convenient dependency injection function for obtaining database sessions in FastAPI routes.

## Files and Their Roles

*   **`database/__init__.py`**:
    *   Initializes the database module.
    *   It imports `Base` from `sqlalchemy.ext.declarative` (or `sqlalchemy.orm.declarative_base`), which is the declarative base class for all SQLAlchemy models in the application.
    *   It also imports `xcfg` from `xcore.appcfg`, making the application's configuration available for database setup.
*   **`database/db.py`**:
    *   Contains the core logic for establishing the database engine and managing sessions.
    *   Defines the `get_db()` function, a FastAPI dependency that provides a SQLAlchemy session to route handlers.

## Key Concepts and Functionality

### SQLAlchemy ORM

The `database` module utilizes **SQLAlchemy**, a powerful and flexible SQL toolkit and Object-Relational Mapper (ORM) for Python.
*   **Declarative Base (`Base`)**: All database models in the application (e.g., `User`, `Role`, `Permission`) inherit from `Base`, allowing them to be mapped to database tables declaratively.

### Database Engine and Session Management

*   **`create_engine`**: The `db.py` file uses `sqlalchemy.create_engine` to establish a connection to the database. The database URL and `echo` setting (for logging SQL queries) are retrieved from `xcfg.custom_config["data"]` (which comes from the `xcore` section of `config.json`).
*   **`sessionmaker`**: A factory for `Session` objects. Sessions are the primary way to interact with the database; they manage persistence operations for ORM-mapped objects.
*   **`get_db()` Dependency**: This is a crucial FastAPI dependency function. When a route handler declares a parameter of type `Session = Depends(get_db)`, FastAPI will:
    1.  Call `get_db()`.
    2.  Obtain a database session.
    3.  Yield this session to the route handler.
    4.  Automatically close the session after the request is finished (ensuring proper resource management).

### Configuration

The database connection details are primarily configured in `config.json` under the `xcore.data` section:

```json
"xcore": {
    "data": {
        "url": "sqlite:///test.db", // The database connection string
        "echo": false              // Set to true to log all SQL statements (useful for debugging)
    },
    // ...
}
```

The `url` can specify various database backends (e.g., SQLite, PostgreSQL, MySQL). For example, `sqlite:///./test.db` for a local SQLite file, or `mysql+pymysql://user:password@host:port/dbname` for MySQL.

## Integration with Other Modules

*   **`xcore/appcfg.py`**: Provides the `xcfg` object which contains the database configuration loaded from `config.json`.
*   **`admin/models.py`**, **`auth/models.py`**, **`otpprovider/models.py`**, **`manager/models/`**: All SQLAlchemy ORM models throughout the application import `Base` from `database/__init__.py` to define their database mappings.
*   **`admin/routes.py`**, **`auth/routes.py`**, **`otpprovider/routes.py`**, **`manager/routes/`**: All API route handlers that interact with the database use `db: Session = Depends(get_db)` to acquire a database session.
*   **`configurations/migrations.py`**: The `migration` configuration section in `config.json` also defines a `url` for Alembic, which should generally match the `xcore.data.url`.
