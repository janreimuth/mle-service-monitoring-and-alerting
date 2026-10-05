"""FastAPI spam detection service used by the monitoring tutorial.

The service deliberately keeps model serving simple so you can focus on
the operational layer: health checks, Prometheus metrics, dashboards and
alerts around a running model API.
"""

import pickle
import re
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

app = FastAPI()
Instrumentator().instrument(app).expose(app)

MODEL_PATH = Path(__file__).with_name("model.bin")

with MODEL_PATH.open("rb") as f_in:
    model = pickle.load(f_in)


class MessageResponse(BaseModel):
    """Response returned by the landing route."""

    message: str


class HealthResponse(BaseModel):
    """Small health payload used by Docker and manual checks."""

    status: str


class PredictionResponse(BaseModel):
    """Prediction payload returned to API callers."""

    label: str
    spam_probability: float


def preprocessor(text: str) -> str:
    """Apply the same lightweight text cleanup used when the model was trained."""
    # Remove HTML tags, such as <br>, before passing text to the model.
    text = re.sub("<[^>]*>", "", text)
    # Preserve simple emoticons because they can carry sentiment-like signal.
    emoticons = re.findall(r"(?::|;|=)(?:-)?(?:\)|\(|D|P)", text)
    # Lowercase words, remove punctuation and append normalized emoticons.
    text = re.sub(r"[\W]+", " ", text.lower()) + " ".join(emoticons).replace("-", "")
    return text


def classify_message(model: Any, message: str) -> PredictionResponse:
    """Preprocess one message, run the model, and return an API response."""

    message = preprocessor(message)
    label = model.predict([message])[0]
    spam_prob = model.predict_proba([message])
    return PredictionResponse(label=label, spam_probability=float(spam_prob[0][1]))


@app.get("/", response_model=MessageResponse)
def get_root():
    """Return a friendly message for browser-based smoke tests."""

    # A simple landing response is useful for quick manual checks in a browser.
    return MessageResponse(message="Welcome to the spam detection API")


@app.get("/health", response_model=HealthResponse)
def get_health():
    """Return service health without invoking the model."""

    # Docker uses this endpoint for the container healthcheck.
    return HealthResponse(status="ok")


@app.get("/spam_detection_path/{message}", response_model=PredictionResponse)
async def detect_spam_path(message: str):
    """Classify a URL-encoded message passed as a path parameter."""

    # The message is passed as a URL path segment in this tutorial.
    return classify_message(model, message)


if __name__ == "__main__":
    # This path is handy for local debugging with `python service/main.py`.
    uvicorn.run(app, host="0.0.0.0", port=8080)
