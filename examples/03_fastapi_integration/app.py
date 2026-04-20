from fastapi import FastAPI
from xcore import Xcore
from contextlib import asynccontextmanager

# Initialize XCore with the local config
core = Xcore(config_path="xcore.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot XCore and its plugins
    await core.boot(app)
    yield
    # Graceful shutdown
    await core.shutdown()

app = FastAPI(title="XCore Weather Service", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Weather Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
