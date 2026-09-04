from fastapi import FastAPI
from app.api.webhooks import app

# Main entry point - imports the FastAPI app from webhooks
# This allows uvicorn to start with: uvicorn app.main:app
