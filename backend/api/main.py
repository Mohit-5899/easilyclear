from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings
from llm import LLMClient, Message, get_llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.llm = get_llm_client(settings)
    yield


app = FastAPI(title="Gemma Tutor Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    ok: bool
    app: str
    env: str
    llm_provider: str


class LLMTestRequest(BaseModel):
    prompt: str = "Say hi in one short sentence."


class LLMTestResponse(BaseModel):
    provider: str
    model: str
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        ok=True,
        app=settings.app_name,
        env=settings.app_env,
        llm_provider=settings.llm_provider,
    )


@app.post("/llm/test", response_model=LLMTestResponse)
async def llm_test(req: LLMTestRequest) -> LLMTestResponse:
    settings = get_settings()
    client: LLMClient = app.state.llm
    try:
        resp = await client.complete(
            messages=[
                Message(role="system", content="You are a concise assistant."),
                Message(role="user", content=req.prompt),
            ],
            model=settings.model_answer,
            temperature=0.3,
            max_tokens=128,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")

    return LLMTestResponse(
        provider=resp.provider,
        model=resp.model,
        content=resp.content,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
    )
