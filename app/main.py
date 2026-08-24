import uvicorn
from fastapi import FastAPI
from app.db.database import engine, Base
from app.api import transactions, recovery, metrics
from app.config import settings

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RecoverAI API",
    description="Autonomous Revenue Recovery API for Razorpay AI Buildathon (Track 03)",
    version="1.0.0"
)

# Include routers
app.include_router(transactions.router, prefix="/api")
app.include_router(recovery.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "ONLINE",
        "service": "RecoverAI",
        "description": "AI-Powered Revenue Recovery Agent",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
