import os
from google import genai

def generate_ai_post(listing_title: str, price: float, area: float, location: str, description: str, tone: str = "chuyen_nghiep"):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    
    prompt = f"""
Bạn là chuyên gia marketing bất động sản hàng đầu. Hãy viết 1 bài đăng Facebook chuyên nghiệp, thu hút khách hàng để bán/cho thuê bất động sản sau:
- Tiêu đề: {listing_title}
- Giá: {price} tỷ VNĐ
- Diện tích: {area} m2
- Vị trí/Địa chỉ: {location}
- Chi tiết mô tả: {description}
- Phong cách: {tone}

Yêu cầu bài viết:
1. Tiêu đề thật giật tít, thu hút có icon emoji phù hợp.
2. Các điểm nổi bật về vị trí, tiềm năng sinh lời, tiện ích xung quanh.
3. Thông tin pháp lý, diện tích, giá bán rõ ràng.
4. Kêu gọi hành động (Call To Action - Liên hệ xem nhà/đất).
5. Hashtag liên quan BĐS.
"""
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"[Gemini AI Error] {e}")

    # Fallback template neu khong co API key hoac gap loi
    return f"""🔥 SIÊU PHẨM BẤT ĐỘNG SẢN HOT NHẤT KHU VỰC - {listing_title.upper()} 🔥

📍 Vị trí đắc địa: {location}
💰 Giá đầu tư chỉ: {price} Tỷ (Thương lượng trực tiếp chính chủ)
📐 Diện tích vàng: {area} m²

✨ ĐẶC ĐIỂM NỔI BẬT:
- {description if description else 'Vị trí giao thông thuận tiện, đường thông thoáng, dân trí cao.'}
- Tiềm năng tăng giá cực cao, thích hợp ở hoặc đầu tư sinh lời ngay.
- Sổ hồng riêng, pháp lý chuẩn chỉnh 100%, sẵn sàng công chứng trong ngày.

📞 LIÊN HỆ NGAY ĐỂ XEM NHÀ/ĐẤT THỰC TẾ & NHẬN GIÁ TỐT NHẤT:
☎ Hotline/Zalo: 0988.xxx.xxx (Hỗ trợ 24/7)

#BatDongSan #NhaDat #DauTuBDS #BDSGiaTot #BatDongSanChinhChu #{location.replace(' ', '')}
"""
