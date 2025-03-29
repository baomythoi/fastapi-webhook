from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import openai
import os
import json
import logging
from datetime import datetime
from openai.error import OpenAIError
import asyncio
import time

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set in environment variables")
openai.api_key = openai_api_key

async def call_openai_api(prompt):
    return await asyncio.wait_for(
        asyncio.to_thread(
            openai.ChatCompletion.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an assistant specialized in extracting order details. Return only pure JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        ),
        timeout=10  # 10 giây timeout
    )

@app.post("/webhook")
async def webhook(request: Request):
    request_id = datetime.now().strftime("%Y%m%d%H%M%S")
    data = await request.json()

    if "message" not in data or not data["message"]:
        logger.error("[%s] Missing 'message' field or empty", request_id)
        return JSONResponse(content={"status": "error", "message": "Input data missing 'message' field or empty"}, status_code=400)

    user_message = data["message"]
    logger.info("[%s] Received data: %s", request_id, data)

    prompt = f"""
    Extract the following information from the message below:
    - Order date (format YYYY-MM-DD, use current date if not specified)
    - Customer name
    - Address
    - Phone number
    - Product name
    - Quantity
    - Note (if any)
    - Delivery time (format YYYY-MM-DD HH:MM, use null if not specified)

    Message: "{user_message}"

    Return the result as pure JSON (no explanations, no additional text). Set missing fields to null. Example:
    {{
      "order_date": "2025-03-28",
      "customer_name": "Nguyen Van A",
      "address": "123 ABC Street, HCMC",
      "phone_number": "0909123456",
      "product_name": "T-shirt",
      "quantity": 2,
      "note": "Fast delivery",
      "delivery_time": "2025-03-29 10:00"
    }}
    """

    for attempt in range(3):
        try:
            response = await call_openai_api(prompt)
            result_json = json.loads(response["choices"][0]["message"]["content"])
            break
        except OpenAIError as e:
            logger.warning("[%s] OpenAI attempt %d error: %s", request_id, attempt + 1, str(e))
            if attempt == 2:
                return JSONResponse(content={"status": "error", "message": f"OpenAI API failed after 3 attempts: {str(e)}"}, status_code=500)
            time.sleep(2)
        except json.JSONDecodeError as e:
            logger.error("[%s] JSONDecodeError: %s", request_id, str(e))
            return JSONResponse(content={"status": "error", "message": f"Invalid JSON from OpenAI: {str(e)}"}, status_code=500)
        except asyncio.TimeoutError:
            logger.warning("[%s] Timeout attempt %d", request_id, attempt + 1)
            if attempt == 2:
                return JSONResponse(content={"status": "error", "message": "OpenAI API timeout after 3 attempts"}, status_code=504)

    result_json["order_id"] = request_id
    logger.info("[%s] GPT result: %s", request_id, result_json)

    return JSONResponse(content={"status": "ok", "result": result_json})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
