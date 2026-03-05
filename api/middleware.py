from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 開發階段允許全部
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )