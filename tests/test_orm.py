"""Every feature's models register on the one shared declarative Base."""

from __future__ import annotations

import app.auth.models as auth_models
import app.events.models as events_models
import app.models as timeseries_models
import app.news.models as news_models
from app.orm import Base


def test_all_model_modules_share_one_base():
    for model in (
        timeseries_models.Source,
        timeseries_models.Entity,
        timeseries_models.Observation,
        news_models.NewsArticle,
        events_models.Event,
        auth_models.User,
        auth_models.Session,
    ):
        assert model.metadata is Base.metadata
    assert {
        "sources",
        "entities",
        "observations",
        "news_articles",
        "events",
        "users",
        "sessions",
    } <= set(Base.metadata.tables)
