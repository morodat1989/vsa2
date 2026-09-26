from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/settings")
def get_settings(request: Request):
    # Đọc API key hiện tại từ file .env để hiển thị lên ô input
    api_key = ""
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
    
    return templates.TemplateResponse(request, "settings.html", {"gemini_api_key": api_key})

@router.post("/settings")
def save_settings(request: Request, gemini_api_key: str = Form(...)):
    env_path = ".env"
    lines = []
    
    # Đọc nội dung cũ nếu có
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    # Kiểm tra xem dòng GEMINI_API_KEY đã tồn tại chưa để cập nhật
    key_found = False
    new_lines = []
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={gemini_api_key}\n")
            key_found = True
        else:
            new_lines.append(line)
            
    # Nếu chưa có thì thêm mới vào cuối
    if not key_found:
        new_lines.append(f"GEMINI_API_KEY={gemini_api_key}\n")
        
    # Ghi lại vào file .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    # Đồng thời load trực tiếp vào biến môi trường chạy hiện tại của Python
    os.environ["GEMINI_API_KEY"] = gemini_api_key
    
    return RedirectResponse(url="/settings?saved=true", status_code=303)