from fastapi import FastAPI
from app.api.v1 import routes as v1_routes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Alpha Arena Recreation",
    description="A simulation of LLM-powered trading agents.",
    version="0.1.0"
)

# CORS middleware to allow the frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API routes
app.include_router(v1_routes.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Alpha Arena Backend. Visit /docs for API details."}