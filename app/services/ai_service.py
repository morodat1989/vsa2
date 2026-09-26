import os
import re
import json
import random
from google import genai

def parse_and_refine_listing_ai(raw_text: str) -> dict:
    """
    Trích xuất và chuẩn hóa bài đăng BĐS chỉ từ 1 ô dán văn bản thô (raw_text).
    Gemini tự động nhận diện: Tiêu đề, Giá (tỷ/triệu), Diện tích (m2), Vị trí, và biên tập lại thành bài đăng chuẩn súc tích có icon + SĐT 0559 431 814.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from app.database import SessionLocal
            from app.models import Setting
            with SessionLocal() as db_session:
                row = db_session.query(Setting).filter(Setting.key == "gemini_api_key").first()
                if row and row.value:
                    api_key = row.value.strip()
                    os.environ["GEMINI_API_KEY"] = api_key
        except Exception:
            pass

    # Regex trích xuất nhanh đề phòng lỗi mạng hoặc không có API key
    fallback_title = "Bất động sản chính chủ"
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
    if lines:
        fallback_title = lines[0].replace("🏠", "").replace("👉", "").replace("💎", "").replace("✨", "").strip()
        if len(fallback_title) > 90:
            fallback_title = fallback_title[:87] + "..."

    # Trích xuất giá sơ bộ
    fallback_price = 0.0
    price_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(tỷ|ty|tr|triệu|trieu)", raw_text, re.IGNORECASE)
    if price_match:
        val = float(price_match.group(1).replace(",", "."))
        unit = price_match.group(2).lower()
        if "t" in unit and ("tr" not in unit and "tri" not in unit):
            fallback_price = val
        else:
            fallback_price = round(val / 1000.0, 3)

    # Trích xuất diện tích sơ bộ
    fallback_area = 50.0
    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|mét)", raw_text, re.IGNORECASE)
    if area_match:
        fallback_area = float(area_match.group(1).replace(",", "."))

    fallback_location = "Hải Phòng"
    for cand in ["Văn Cao", "Lê Hồng Phong", "Dư Hàng", "Hoàng Huy", "Cầu Rào", "Dương Kinh", "Cầu Giấy", "Hà Nội"]:
        if cand.lower() in raw_text.lower():
            fallback_location = cand
            break

    structured = {
        "title": fallback_title,
        "price": fallback_price,
        "area": fallback_area,
        "location": fallback_location,
        "description": raw_text.strip(),
        "refined_content": f"""🏠 {fallback_title.upper()}
📍 Vị trí: {fallback_location}
💰 Giá: {fallback_price if fallback_price else 'Thỏa thuận'}
✨ Diện tích: {fallback_area} m²
👉 Thông tin chi tiết:
{raw_text.strip()}
☎️ SĐT/Zalo: 0559 431 814"""
    }

    if not api_key:
        return structured

    prompt = f"""
Bạn là chuyên gia thẩm định và copywriting BĐS tại Việt Nam. 
Người dùng dán nội dung thông tin một bất động sản sau đây:

\"\"\"
{raw_text}
\"\"\"

Nhiệm vụ của bạn:
1. Trích xuất thông tin có cấu trúc chuẩn xác:
   - title: Tiêu đề BĐS ngắn gọn, giật tít thu hút (dưới 85 ký tự, ví dụ: "Cho thuê nguyên căn Văn Cao siêu đẹp 5PN", "Bán nhà dân xây mặt đường đôi Lê Hồng Phong").
   - price: Giá quy đổi ra đơn vị TỶ VNĐ (số thực float). Ví dụ: 25 triệu -> 0.025, 16 triệu -> 0.016, 6.3 tỷ -> 6.3, 15.5 tỷ -> 15.5, nếu thỏa thuận/không rõ ghi 0.
   - area: Diện tích m2 (số thực float, ví dụ 80, 49.5, 200).
   - location: Vị trí / Địa chỉ ngắn gọn (ví dụ: "Văn Cao, Hải Phòng", "Hoàng Huy Riverside, Chi Lăng", "Lê Hồng Phong, Hải Phòng").
   - description: Tóm tắt lại công năng & tiện ích chính (ví dụ: "5 ngủ khép kín, full đồ, ô tô đỗ cửa, bìa đỏ chính chủ").
   - refined_content: Biên tập lại toàn bộ bài viết theo đúng phong cách môi giới THỰC CHIẾN: NGẮN GỌN, SÚC TÍCH, DÙNG ICON ĐẦU DÒNG (*, 👉, 📍, 💰, ✨, 🏠, 📕, ☎️) và BẮT BUỘC DÒNG CUỐI LÀ "☎️ SĐT/Zalo: 0559 431 814".

CHỈ TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ THEO ĐỊNH DẠNG NÀY (Không có bất kỳ chữ nào khác):
{{
  "title": "Tiêu đề BĐS",
  "price": 6.3,
  "area": 49.5,
  "location": "Lê Hồng Phong, Hải Phòng",
  "description": "Nhà dân xây độc lập, ô tô vào nhà, bìa đỏ chính chủ",
  "refined_content": "Bài viết hoàn chỉnh có icon và SĐT 0559 431 814"
}}
"""
    candidate_models = ["gemini-flash-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]
    for model_name in candidate_models:
        try:
            client = genai.Client(api_key=api_key)
            res = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if res and res.text:
                txt = res.text.strip()
                # Loại bỏ markdown code blocks nếu có
                if txt.startswith("```"):
                    txt = re.sub(r"^```(?:json)?", "", txt)
                    txt = re.sub(r"```$", "", txt).strip()
                data = json.loads(txt)
                if isinstance(data, dict) and "title" in data:
                    # Đảm bảo chắc chắn có đúng SĐT/Zalo
                    if "refined_content" in data and "0559 431 814" not in data["refined_content"]:
                        data["refined_content"] += "\n☎️ SĐT/Zalo: 0559 431 814"
                    return data
        except Exception:
            continue

    return structured


def build_default_listing_content(listing_title: str, price: float, area: float, location: str, description: str) -> str:
    """
    Tạo nội dung mặc định hiển thị tức thì (0ms, không lag, không gọi Gemini ở Bước 1).
    Chuẩn mẫu môi giới thực chiến, ngắn gọn, có icon và số SĐT/Zalo 0559 431 814.
    """
    price_display = f"{price:g} tỷ" if price >= 1.0 else f"{int(price * 1000)} triệu"
    if price == 0:
        price_display = "Thỏa thuận"

    return f"""🏠 {listing_title.upper()}
📍 Vị trí: {location}
💰 Giá: {price_display} (có thoả thuận)
✨ Diện tích: {area} m²
👉 Mô tả & Công năng: {description if description else 'Vị trí đẹp, dân trí cao, giao thông thuận tiện.'}
📕 Pháp lý: Sổ đỏ chính chủ
☎️ SĐT/Zalo: 0559 431 814"""

def generate_ai_post(listing_title: str, price: float, area: float, location: str, description: str, tone: str = "chuyen_nghiep"):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from app.database import SessionLocal
            from app.models import Setting
            with SessionLocal() as db_session:
                row = db_session.query(Setting).filter(Setting.key == "gemini_api_key").first()
                if row and row.value:
                    api_key = row.value.strip()
                    os.environ["GEMINI_API_KEY"] = api_key
        except Exception:
            pass
    
    # Định dạng giá tiền thông minh
    price_display = f"{price:g} tỷ" if price >= 1.0 else f"{int(price * 1000)} triệu"
    if price == 0:
        price_display = "Thỏa thuận"

    prompt = f"""
Bạn là chuyên viên môi giới bất động sản thực chiến tại Hải Phòng và các tỉnh thành Việt Nam.
Hãy viết một bài đăng Facebook bán/cho thuê bất động sản theo đúng PHONG CÁCH MÔI GIỚI THỰC CHIẾN: NGẮN GỌN, SÚC TÍCH, DÙNG ICON ĐẦU DÒNG (*, 👉, 📍, 💰, ✨, 🏠, 📕, ☎️) giống hệt các mẫu thực tế sau:

--- CÁC MẪU CHUẨN THỰC TẾ: ---
Mẫu 1:
Cho thuê nguyên căn tại Văn Cao siêu xịn 
👉 Diện tích : 80 m2 x 4.5 tầng 
👉 Cấu trúc : 5 ngủ khép kín 
👉 Full đồ siêu đẹp 
👉 Thuận lợi đi lại 
👉 Khách chỉ cần xách vali về để ở 
💵 Giá cho thuê : 25 tr (thoả thuận nhẹ)
☎️ SĐT/Zalo: 0559 431 814

Mẫu 2:
Cho thuê tầng 1 + 2 mặt đường Chi Lăng thuộc Hoàng Huy Reverside
*Giá : 16tr (thoả thuận)
*Diện tích : 85m2, mặt tiền 6m, vỉa hè 3m
*Nhà thuộc dự án Hoàng Huy Reverside mặt đường Chi Lăng
*Công năng : cho thuê tầng 1 + 2
*Pháp lý : sổ đỏ chính chủ
*SĐT/Zalo: 0559 431 814

Mẫu 3:
🏡 BÁN NHÀ DÂN XÂY ĐỘC LẬP – MẶT ĐƯỜNG ĐÔI KHU PHÂN LÔ LÊ HỒNG PHONG
📍 Vị trí đẹp, lô 9 Lê Hồng Phong, đường trước nhà 30m, giao thông cực kỳ thuận tiện.
✨ Diện tích: 49,5m² – ngang 4,5m
🏠 Nhà dân xây độc lập, kết cấu chắc chắn
📕 Bìa đỏ chính chủ
💰 Giá: 6,3 tỷ
☎️ SĐT/Zalo: 0559 431 814
------------------------------

THÔNG TIN BẤT ĐỘNG SẢN CẦN VIẾT:
- Tiêu đề: {listing_title}
- Giá: {price_display}
- Diện tích: {area} m²
- Vị trí/Địa chỉ: {location}
- Chi tiết mô tả/Công năng: {description}

YÊU CẦU BẮT BUỘC:
1. BỐ CỤC NGẮN GỌN, SÚC TÍCH: Tuyệt đối không viết văn dài dòng, không lan man, không viết đoạn văn miêu tả hoa mỹ kiểu quảng cáo chung chung.
2. DÙNG CÁC ĐẦU DÒNG CÓ ICON (như 👉 hoặc * hoặc 📍, ✨, 🏠, 💰, 📕, ☎️) cho từng thông số: Giá, Diện tích, Vị trí, Công năng/Mô tả, Pháp lý.
3. BẮT BUỘC DÒNG LIÊN HỆ CUỐI BÀI PHẢI LÀ:
☎️ SĐT/Zalo: 0559 431 814
4. Trả về trực tiếp nội dung bài đăng Facebook (không thêm lời chào, không thêm markdown ```).
"""
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            candidate_models = ["gemini-flash-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if response and response.text:
                        text = response.text.strip()
                        # Đảm bảo chắc chắn có đúng SĐT/Zalo của khách
                        if "0559 431 814" not in text:
                            text += "\n☎️ SĐT/Zalo: 0559 431 814"
                        return text
                except Exception:
                    continue
        except Exception as e:
            print(f"[Gemini AI Notice] {e}")

    # Fallback template ngắn gọn súc tích đúng chuẩn môi giới thực chiến
    return f"""🏠 {listing_title.upper()}
📍 Vị trí: {location}
💰 Giá: {price_display} (có thoả thuận)
✨ Diện tích: {area} m²
👉 Mô tả & Công năng: {description if description else 'Vị trí đẹp, dân trí cao, giao thông thuận tiện.'}
📕 Pháp lý: Sổ đỏ chính chủ
☎️ SĐT/Zalo: 0559 431 814
"""

def generate_marketplace_data(listing_title: str, price: float, area: float, location: str, description: str):
    """
    Tạo dữ liệu chuẩn hóa đặc thù cho Facebook Marketplace:
    - Tiêu đề ngắn gọn < 100 ký tự (không dùng ALL CAPS toàn bộ, không emoji rác để tránh bị Marketplace từ chối)
    - Giá bán chính xác
    - Mô tả tuân thủ nghiêm ngặt chính sách thương mại của Facebook
    """
    clean_title = f"Bán {listing_title}".strip()
    if len(clean_title) > 95:
        clean_title = clean_title[:92] + "..."

    price_vnd = int(price * 1_000_000_000) if price else 0

    clean_desc = f"""Vị trí: {location}
Diện tích: {area} m²
Pháp lý: Sổ hồng riêng chính chủ

Thông tin chi tiết:
{description if description else 'Nhà đẹp, vị trí trung tâm, giao thông thuận tiện, an ninh tốt, gần trường học và chợ.'}

Liên hệ xem nhà/đất và thương lượng giá:
☎️ SĐT/Zalo: 0559 431 814
"""
    return {
        "title": clean_title,
        "price_vnd": price_vnd,
        "category": "Bán bất động sản",
        "condition": "Mới",
        "location": location,
        "description": clean_desc
    }

def generate_spintax_variation(base_text: str, group_index: int = 1) -> str:
    """
    Tạo biến thể nội dung tự nhiên cho từng nhóm (chỉ khi đăng qua nhiều nhóm)
    để bài đăng tự nhiên, không bị Facebook đánh giá spam mà vẫn giữ trọn vẹn nội dung gốc.
    TUYỆT ĐỐI KHÔNG chèn [Mã tin: BDS-xxxx] gây mất mỹ quan và phản cảm cho khách hàng.
    """
    if not base_text:
        return base_text

    text = base_text.strip()
    
    # Đối với nhóm đầu tiên (hoặc khi chỉ đăng 1 nhóm), giữ nguyên vẹn 100% nội dung gốc
    if group_index <= 1:
        return text

    # Đối với các nhóm tiếp theo, thay đổi nhẹ câu chào kết bài một cách chuyên nghiệp
    closers = [
        "🤝 Tiếp khách thiện chí, làm việc trực tiếp chủ nhà không qua trung gian!",
        "📲 Liên hệ xem nhà 24/7, hỗ trợ thủ tục công chứng sang tên nhanh chóng!",
        "⚡ Cam kết thông tin thật 100%, hình ảnh thực tế, thương lượng giá tốt!",
        "👉 Quý anh/chị quan tâm vui lòng inbox hoặc liên hệ hotline để nhận thêm thông tin chi tiết!"
    ]
    subtle_closer = closers[(group_index - 1) % len(closers)]

    # Nếu câu kết này chưa có trong bài viết thì bổ sung nhẹ nhàng ở cuối
    if subtle_closer not in text:
        return f"{text}\n\n{subtle_closer}"
    return text
