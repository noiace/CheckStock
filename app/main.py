from fastapi import FastAPI
import uvicorn

app = FastAPI()

app.include_router()

def main():
    print("Hello from test-task!")

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
