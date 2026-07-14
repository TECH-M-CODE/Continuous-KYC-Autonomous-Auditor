from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SentinelAI API",
    description="SentinelAI Continuous KYC Autonomous Auditor API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {
        "success": True,
        "message": "SentinelAI API is healthy",
        "data": {
            "status": "healthy",
            "db_connected": True
        }
    }

@app.get("/")
async def root():
    return {
        "message": "Welcome to SentinelAI Continuous KYC Auditor API"
    }
