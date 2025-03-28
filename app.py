from fastapi import FastAPI

app = FastAPI()

@app.get("/webhook")
async def webhook():
    return {"message": "Hello from FastAPI webhook!"}
