from typing import Any, Mapping
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from whatsapp_receive.queue import push_to_queue
from whatsapp_receive.security import verify_webhook
import logging
from mangum import Mangum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Webhook")
handler = Mangum(app)

@app.get("/health")
async def health() -> Mapping[str, Any]:
    return {"status": "healthy"}

@app.get("/webhook")
async def webhook_verify(request: Request) -> Response:
    params = dict(request.query_params)
    logger.info(f"Params from webhook_verify: {params}")
    content, status = verify_webhook(params)
    if isinstance(content, str):
        # Meta expects the plain challenge string
        logger.info(f"Content from webhook_verify: {content}")
        return PlainTextResponse(content, status_code=status)
    return JSONResponse(content, status_code=status)

@app.post("/webhook")
async def webhook_receive(request: Request) -> JSONResponse:
    raw_body = await request.body()
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON body: {e}")
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)
        
    logger.info(f"Body from webhook_receive: {body}")
    headers = {k: v for k, v in request.headers.items()}
    content, status = push_to_queue(body, headers, raw_body)
    return JSONResponse(content, status_code=status)