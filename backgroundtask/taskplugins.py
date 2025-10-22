import time



metadata = {
    "title": "Plugins Listerner",
    "description": """
        This service is a plugins service to analyse
        all plugins dir modification to update app and plugins

    """,
    "version": "1.0.0",
    "author": "Root",
    "type": "Listerner",
    "module": "core",
    "moduleDir": "Root",
    "status": True,
    "dependencies": ["core"],
    "license": "MIT",
    "tags": [".", "listener", "plugins"],
    "icon": "mdi:message-text",
    "homepage": "app/feelback",
    "documentation": "http://app.tangagroup.com/docs/core/listener",
    "repository": "http://app.tangagroup.com/repo/core/listener",
    "issues": "http://app.tangagroup.com/issues/core/listener",
    "changelog": "http://app.tangagroup.com/changelog/core/listener",
    "support": "http://app.tangagroup.com/support/core/listener",
    "contact": {
        "email": "contact@tangagroup.com",
        "website": "http://app.tangagroup.com",
        "phone": "+1234567890",
    },
    "keywords": ["core", "listener", "service", "plugins"],
    "created_at": "2023-10-01T00:00:00Z",
    "updated_at": "2023-10-01T00:00:00Z",
    "license_url": "http://app.tangagroup.com/license",
    "con": [
        {
            "func": lambda: print("hello world"),
            "name": "delete all sesion expirate",
            "misfire_grace_time": 10,
            "interval": "interval",
            "minutes": 1,
            "activate": True,
        }
    ],
}


def service_main(service):

    from main import manager

    while service.running:
        manager.start_watching(service)
        print("starred plugin manager snapshot" " - Next check in 2 seconds...")
        time.sleep(2)
    print("Stopping plugin manager service...")
    return True
