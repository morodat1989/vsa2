import { GoogleGenAI } from '@google/genai';
import { db } from './db.js';

export async function generatePostContent(listing, style = 'engaging', customInstructions = '') {
  const settings = db.getSettings();
  const apiKey = settings.gemini_api_key || process.env.GEMINI_API_KEY;

  const stylePrompts = {
    engaging: "Phong cách hấp dẫn, giật tít thu hút người mua nhà, sử dụng icon emoji sinh động, làm nổi bật tiện ích sống và tiềm năng sinh lời.",
    urgent: "Phong cách cấp bách, cần bán gấp hạ giá, chủ cần tiền gấp giải quyết việc gia đình, tạo cảm giác khan hiếm và cơ hội đầu tư siêu hời.",
    professional: "Phong cách chuyên nghiệp, văn phong sang trọng, thông tin chi tiết minh bạch, phù hợp khách hàng mua ở thực và nhà đầu tư sành sỏi."
  };

  const selectedStyle = stylePrompts[style] || stylePrompts.engaging;

  const prompt = `Bạn là một chuyên gia marketing bất động sản và copywriting mạng xã hội hàng đầu tại Việt Nam.
Hãy viết một bài đăng Facebook bán bất động sản cực kỳ cuốn hút, chuẩn SEO Facebook, có bố cục rõ ràng với các biểu tượng cảm xúc (emoji) phù hợp, kêu gọi hành động (CTA) mạnh mẽ và hashtag liên quan.

THÔNG TIN BẤT ĐỘNG SẢN:
- Tiêu đề: ${listing.title}
- Vị trí/Địa chỉ: ${listing.address}
- Giá bán: ${listing.price ? listing.price + ' Tỷ' : 'Thỏa thuận'}
- Diện tích: ${listing.area ? listing.area + ' m²' : 'Chưa rõ'}
- Kết cấu/Phòng: ${listing.bedrooms ? listing.bedrooms + ' Phòng ngủ' : ''} ${listing.bathrooms ? ', ' + listing.bathrooms + ' WC' : ''}
- Hướng: ${listing.direction || 'Đông Nam'}
- Pháp lý: ${listing.legal || 'Sổ hồng riêng, công chứng ngay'}
- Nội thất: ${listing.interior || 'Đầy đủ'}
- Người liên hệ: ${listing.contact_name || 'Chính chủ'}
- Số điện thoại/Zalo: ${listing.contact_phone || 'Liên hệ ngay'}
- Mô tả chi tiết: ${listing.description || ''}

YÊU CẦU NỘI DUNG:
- ${selectedStyle}
${customInstructions ? `- Yêu cầu thêm từ người dùng: ${customInstructions}` : ''}
- Hãy viết trực tiếp nội dung bài đăng Facebook (không cần lời chào đầu hay giải thích của AI).
- Bao gồm tiêu đề giật tít, các điểm nhấn (bullet points), thông số kỹ thuật, giá cả, thông tin liên hệ và các hashtag thị trường BĐS.`;

  if (apiKey) {
    try {
      const ai = new GoogleGenAI({ apiKey });
      const model = settings.gemini_model || 'gemini-2.5-flash';
      const response = await ai.models.generateContent({
        model: model,
        contents: prompt,
      });

      if (response && response.text) {
        return response.text.trim();
      }
    } catch (err) {
      console.warn("Gemini API call failed or quota exceeded, using smart fallback template:", err.message);
    }
  }

  // Fallback high-quality template if API key is not yet configured
  return generateFallbackTemplate(listing, style);
}

function generateFallbackTemplate(listing, style) {
  const priceStr = listing.price ? `${listing.price} TỶ` : 'GIÁ TỐT';
  const areaStr = listing.area ? `${listing.area}m²` : '';
  const phone = listing.contact_phone || '0908.xxx.xxx';
  const contact = listing.contact_name || 'Chuyên viên BĐS';

  if (style === 'urgent') {
    return `🚨 CHỦ NGỘP BANK CẦN BÁN GẤP TRONG TUẦN - GIÁ SẬP HẦM 🚨

💥 ${listing.title.toUpperCase()}
📍 Vị trí: ${listing.address}
💰 Giá bán: ${priceStr} (Thương lượng chính chủ cho khách thiện chí chốt nhanh)
📐 Diện tích: ${areaStr} ${listing.bedrooms ? `| ${listing.bedrooms}PN - ${listing.bathrooms || 1}WC` : ''}

⭐ ĐẶC ĐIỂM NỔI BẬT:
✅ ${listing.description || 'Vị trí vàng, giao thông thuận tiện, khu dân cư an ninh.'}
✅ Pháp lý chuẩn chỉnh: ${listing.legal || 'Sổ hồng riêng, sẵn sàng công chứng sang tên ngay'}
✅ Hướng: ${listing.direction || 'Đông Nam'} - Vượng khí tài lộc
✅ Nội thất: ${listing.interior || 'Bàn giao hoàn thiện cao cấp'}

⚡ Cơ hội bắt đáy bất động sản sinh lời ngay 15-20%!
📞 Liên hệ xem nhà 24/7: ${phone} (${contact})
💬 Hỗ trợ tư vấn pháp lý & vay ngân hàng lãi suất ưu đãi.

#BatDongSan #NhaDatChinhChu #BanNhaGap #HaGia #BatDongSanGiaRe`;
  }

  if (style === 'professional') {
    return `🏢 CƠ HỘI ĐẦU TƯ & AN CƯ LÝ TƯỞNG
${listing.title.toUpperCase()}

Kính gửi Quý khách hàng thông tin chi tiết bất động sản:
▫️ Địa chỉ: ${listing.address}
▫️ Diện tích: ${areaStr}
▫️ Thiết kế: ${listing.bedrooms ? `${listing.bedrooms} phòng ngủ, ${listing.bathrooms || 1} phòng tắm` : 'Hiện đại, tối ưu công năng'}
▫️ Hướng bất động sản: ${listing.direction || 'Đông Nam'}
▫️ Tình trạng pháp lý: ${listing.legal || 'Sổ đỏ/Sổ hồng chính chủ, giao dịch an toàn'}
▫️ Tình trạng bàn giao: ${listing.interior || 'Nội thất đầy đủ chất lượng cao'}

Mức giá niêm yết: ${priceStr}
Chi tiết quy hoạch và mô tả:
${listing.description || 'Khu dân cư hiện hữu văn minh, tiện ích ngoại khu đồng bộ trong bán kính 1km.'}

Quý khách quan tâm vui lòng liên hệ bộ phận kinh doanh để nhận trọn bộ tài liệu pháp lý và lịch tham quan thực tế:
☎️ Hotline: ${phone} (Mr/Ms ${contact})

#RealEstate #BatDongSanChuyenNghiep #NhaDep #DauTuSinhLoi`;
  }

  // Default: engaging
  return `🔥 SIÊU PHẨM BẤT ĐỘNG SẢN CỰC ĐẸP - VỊ TRÍ ĐẮC ĐỊA 🔥

🏡 ${listing.title}
📍 Vị trí: ${listing.address}
💎 Mức giá cực hấp dẫn: ${priceStr}
📐 Diện tích rộng rãi: ${areaStr} (${listing.bedrooms ? `${listing.bedrooms} Phòng ngủ | ${listing.bathrooms || 1} WC` : 'Thiết kế thông minh'})

✨ ĐIỂM CỘNG ĐÁNG TIỀN:
🔹 ${listing.description || 'Khu vực phát triển vượt bậc, tiện ích vây quanh không thiếu thứ gì.'}
🔹 Hướng nhà: ${listing.direction || 'Đông Nam'} mát mẻ quanh năm, hút tài lộc
🔹 Pháp lý: ${listing.legal || 'Sổ hồng riêng chính chủ, công chứng sang tên trong ngày'}
🔹 Nội thất: ${listing.interior || 'Full nội thất cao cấp chỉ việc xách vali vào ở'}

🎁 Tặng ngay gói bảo hiểm nhà ở và chiết khấu cho khách hàng chốt sớm!
☎️ GỌI NGAY ĐỂ XEM NHÀ TRỰC TIẾP: ${phone} (${contact})
👉 Nhắn tin Zalo/Inbox để nhận video thực tế và vị trí ghim map!

#NhaDep #BatDongSan #MuaBanNhaDat #NhaPho #DauTu`;
}
