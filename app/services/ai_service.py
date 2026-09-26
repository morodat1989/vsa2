import os
import random
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
6. TUÂN THỦ NGUYÊN TẮC CỘNG ĐỒNG FACEBOOK: Không cam kết tài chính phi thực tế, không dùng từ ngữ spam gây hiểu lầm.
"""
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"[Gemini AI Error] {e}")

    # Fallback template an toàn, chuẩn phong cách BĐS
    return f"""🔥 SIÊU PHẨM BẤT ĐỘNG SẢN HOT NHẤT KHU VỰC - {listing_title.upper()} 🔥

📍 Vị trí đắc địa: {location}
💰 Giá đầu tư chỉ: {price} Tỷ (Thương lượng trực tiếp chính chủ)
📐 Diện tích: {area} m²

✨ ĐẶC ĐIỂM NỔI BẬT:
- {description if description else 'Vị trí giao thông thuận tiện, đường thông thoáng, dân trí cao an ninh tốt.'}
- Tiềm năng tăng giá cực cao, thích hợp ở hoặc đầu tư sinh lời ngay.
- Sổ hồng riêng chính chủ, pháp lý chuẩn chỉnh 100%, sẵn sàng công chứng trong ngày.

📞 LIÊN HỆ NGAY ĐỂ XEM NHÀ/ĐẤT THỰC TẾ & NHẬN GIÁ TỐT NHẤT:
☎ Hotline/Zalo: 0988.xxx.xxx (Hỗ trợ tư vấn tận tâm 24/7)

#BatDongSan #NhaDat #DauTuBDS #BDSGiaTot #BatDongSanChinhChu #{location.split(',')[0].replace(' ', '')}
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

Liên hệ chính chủ để xem nhà và thương lượng giá tốt:
Hotline: 0988.xxx.xxx (Zalo trao đổi thêm hình ảnh sổ sách)
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
    Tự động tạo biến thể nội dung cho từng nhóm để tránh thuật toán phát hiện spam trùng lặp của Facebook:
    - Đổi câu mở đầu (Hook)
    - Thay đổi emoji
    - Đảo vị trí các cụm từ
    - Thêm mã định danh ngẫu nhiên nhỏ kín đáo ở cuối
    """
    openers = [
        "🔥 CHÍNH CHỦ GỬI BÁN CĂN NHÀ ĐẸP HIẾM CÓ!",
        "💎 SIÊU PHẨM BẤT ĐỘNG SẢN GIÁ ĐẦU TƯ CỰC TỐT!",
        "🏡 CẦN NHƯỢNG LẠI NHÀ ĐẸP VỊ TRÍ ĐẮC ĐỊA, SỔ SẴN!",
        "⭐ CƠ HỘI AN CƯ & ĐẦU TƯ SINH LỜI KHÔNG THỂ BỎ LỠ!",
        "🚀 BÁN GẤP TRONG TUẦN - GIÁ TỐT NHẤT KHU VỰC!"
    ]
    
    closers = [
        "👉 Quý anh/chị quan tâm vui lòng inbox hoặc liên hệ hotline để nhận hình ảnh sổ chi tiết!",
        "🤝 Tiếp khách thiện chí, làm việc trực tiếp chủ nhà không qua trung gian!",
        "📲 Liên hệ xem nhà 24/7, hỗ trợ thủ tục công chứng sang tên trọn gói!",
        "⚡ Cam kết thông tin thật 100%, hình ảnh thực tế, thương lượng trực tiếp!"
    ]

    selected_opener = openers[group_index % len(openers)]
    selected_closer = closers[group_index % len(closers)]
    
    # Ghép biến thể nội dung
    unique_tag = f"\n\n[Mã tin: BDS-{random.randint(1000, 9999)}]"
    return f"{selected_opener}\n\n{base_text}\n\n{selected_closer}{unique_tag}"
