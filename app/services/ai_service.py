import os
from google import genai

# Khởi tạo client một lần toàn cục để tái sử dụng kết nối, giúp tăng tốc độ gọi API
_client_instance = None

def get_gemini_client():
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
                    
    if api_key:
        _client_instance = genai.Client(api_key=api_key)
    return _client_instance

def generate_ai_content(listing):
    client = get_gemini_client()
    if not client:
        return {
            "marketplace_title": "Chưa có Gemini API Key",
            "marketplace_desc": "Vui lòng vào Settings để cập nhật API Key.",
            "group_content": "Vui lòng vào Settings để cập nhật API Key."
        }

    # Prompt tối ưu tốc độ kết hợp quy tắc an toàn tránh quét cộng đồng Facebook
    prompt = f"""
    Bạn là một chuyên gia Marketing Bất động sản thực chiến. Dựa vào thông tin căn nhà sau, hãy viết nội dung đăng Facebook:
    - Tiêu đề: {listing.title}
    - Mã: {listing.listing_code} | Giá: {listing.price} | Diện tích: {listing.area}
    - Thông số: {listing.floors} tầng, {listing.bedrooms} ngủ, {listing.bathrooms} vệ sinh
    - Mô tả: {listing.description}

    QUY TẮC AN TOÀN TRÁNH QUÉT CỘNG ĐỒNG (QUAN TRỌNG):
    - Không dùng các từ ngữ giật tít quá đà, từ ngữ nhạy cảm về tài chính hay phân biệt đối xử dễ bị Facebook đánh dấu vi phạm chính sách quảng cáo/nhà ở.
    - Dùng văn phong chia sẻ tự nhiên, thân thiện, mang tính review thực tế đời thường để chống spam và tránh bị bot Facebook bóp tương tác.
    - Phải luôn luôn đính kèm số điện thoại liên hệ: 0559.431.814 vào cuối bài.

    Trả về đúng định dạng cấu trúc tags sau:
    [MARKETPLACE_TITLE]
    (Tiêu đề ngắn gọn dưới 50 ký tự, chứa từ khóa chính ngay đầu)
    
    [MARKETPLACE_DESC]
    (Nội dung Marketplace ngắn gọn, thông số rõ ràng, thân thiện, kèm số ĐT 0559.431.814 ở cuối)
    
    [GROUP_CONTENT]
    (Bài viết đăng nhóm dạng review tự nhiên, giàu thiện cảm, có hashtag gọn gàng và kèm số ĐT 0559.431.814 ở cuối)
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        text = response.text
        
        mp_title, mp_desc, group_cnt = "", "", ""
        
        if "[MARKETPLACE_TITLE]" in text and "[MARKETPLACE_DESC]" in text:
            parts = text.split("[MARKETPLACE_DESC]")
            mp_title = parts[0].replace("[MARKETPLACE_TITLE]", "").strip()
            
            rest = parts[1]
            if "[GROUP_CONTENT]" in rest:
                sub_parts = rest.split("[GROUP_CONTENT]")
                mp_desc = sub_parts[0].strip()
                group_cnt = sub_parts[1].strip()
            else:
                mp_desc = rest.strip()
        else:
            group_cnt = text

        return {
            "marketplace_title": mp_title or listing.title,
            "marketplace_desc": mp_desc or listing.description,
            "group_content": group_cnt or text
        }
    except Exception as e:
        return {
            "marketplace_title": "Lỗi gọi Gemini AI",
            "marketplace_desc": str(e),
            "group_content": str(e)
        }