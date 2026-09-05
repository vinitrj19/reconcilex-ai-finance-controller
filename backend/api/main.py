from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import health, dashboard, reconciliation, exceptions, audit, evaluation, runs

app = FastAPI(title="ReconcileX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reconciliation.router, prefix="/api/v1")
app.include_router(exceptions.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
