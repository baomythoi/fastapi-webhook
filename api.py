from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class RequestBody(BaseModel):
    message: str

@app.post("/process_order")
async def process_order(body: RequestBody):
    return {"received_message": body.message}

