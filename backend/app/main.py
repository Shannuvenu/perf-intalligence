import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, recommendations, runs, sites, stabilization, trends, urls
from app.core.config import get_settings
from app.scheduler.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.ENV != "test":
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Perf Intelligence",
    description="Internal performance & accessibility intelligence tool for Deccan Herald and Prajavani.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sites.router)
app.include_router(urls.router)
app.include_router(urls.url_router)
app.include_router(runs.router)
app.include_router(stabilization.router)
app.include_router(recommendations.router)
app.include_router(trends.router)
