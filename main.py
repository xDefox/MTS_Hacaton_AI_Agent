from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="MTS AI Agent API", version="1.0.0")

# Обязательно сразу включаем CORS, чтобы Flet / Web-фронт не ругались
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. Схема входящего запроса (что шлет фронтенд/телефония)
class CallRequest(BaseModel, extra="allow"):
    session_id: str
    user_message: str  # Текст реплики клиента (или расшифровка STT)
    client_phone: Optional[str] = "unknown"


# 2. Схема ответа (что фронтенд ждет от бэкенда)
class CallResponse(BaseModel):
    agent_response: str  # Что говорит ИИ-агент клиенту
    is_critical: bool  # Критичное ли обращение (важный критерий МТС!)
    intent: str  # Категория вопроса (жалоба, подключение, экстренно)
    action_required: str  # Рекомендация: 'continue_dialog' или 'transfer_to_human'


@app.post("/api/v1/process_call", response_model=CallResponse)
async def process_call(data: CallRequest):
    try:
        # Здесь будет логика вашего ИИ-бэкендера (вызов LLM, анализ)
        # Пока делаем заглушку, чтобы фронтенд мог верстаться параллельно:

        # Эмуляция логики анализа важности
        text_lower = data.user_message.lower()
        is_critical = any(word in text_lower for word in ["срочно", "проблема", "мошенники", "списали", "авария"])

        response_text = "Здравствуйте! Я вас услышал, фиксирую обращение." if not is_critical \
            else "Понимаю вашу тревогу, это важный вопрос."

        return CallResponse(
            agent_response=response_text,
            is_critical=is_critical,
            intent="support_request",
            action_required="transfer_to_human" if is_critical else "continue_dialog"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}