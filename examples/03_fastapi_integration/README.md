# FastAPI Integration Example

How to boot XCore within a FastAPI application.

```python
from fastapi import FastAPI
from xcore import Xcore

app = FastAPI()
core = Xcore(config_path="xcore.yaml")

@app.on_event("startup")
async def startup():
    await core.boot(app)

@app.on_event("shutdown")
async def shutdown():
    await core.shutdown()
```
