# VSA2 – FB Tool Quản Lý Bất Động Sản

VSA2 là ứng dụng web hỗ trợ quản lý nguồn tin bất động sản, tài khoản/profile Facebook, nhóm Facebook và lịch sử đăng bài. Ứng dụng có thể dùng Google Gemini để soạn nội dung đăng tin bằng AI.

> **Lưu ý:** Chỉ sử dụng công cụ với tài khoản, dữ liệu và nhóm mà bạn có quyền quản lý. Hãy tuân thủ Điều khoản dịch vụ của Facebook, chính sách chống spam và pháp luật hiện hành. Không đưa cookie, access token hoặc API key vào Git.

## Tính năng

- Dashboard tổng quan hệ thống.
- Quản lý tin bất động sản: thêm, sửa, xóa, xóa hàng loạt và cập nhật trạng thái.
- Quản lý tài khoản/profile Facebook.
- Quản lý và quét danh sách nhóm Facebook.
- Soạn nội dung tin đăng bằng Google Gemini AI.
- Đăng bài vào nhóm và theo dõi lịch sử đăng bài.
- Cấu hình hệ thống, thời gian chờ và kiểm tra kết nối Gemini.
- Lưu dữ liệu cục bộ, phù hợp để chạy trong môi trường local.

## Công nghệ sử dụng

- **Backend chính:** Python, FastAPI, Uvicorn, SQLAlchemy
- **Giao diện:** Jinja2, EJS, HTML, JavaScript, CSS
- **Tích hợp AI:** Google Gemini (`@google/genai` / `google-genai`)
- **Tự động hóa trình duyệt:** Selenium và Ungoogled Chromium
- **Cơ sở dữ liệu:** SQLAlchemy và dữ liệu cục bộ của ứng dụng
- **Hỗ trợ thay thế:** Node.js, Express và EJS

## Yêu cầu hệ thống

- Windows (các file `.bat` được cung cấp cho Windows).
- Python 3.10 trở lên.
- Node.js 18 trở lên nếu chạy phiên bản Express.
- Ungoogled Chromium tùy chọn; nếu không tìm thấy, ứng dụng sẽ mở trình duyệt mặc định.
- Google Gemini API key nếu muốn sử dụng chức năng AI.

## Cài đặt và chạy bằng Python/FastAPI

Đây là cách khởi chạy được cấu hình trong `start.bat`.

### 1. Tạo môi trường ảo

```powershell
py -m venv venv
```

Nếu lệnh `py` không có trên máy, dùng:

```powershell
python -m venv venv
```

### 2. Kích hoạt môi trường ảo

```powershell
venv\Scripts\activate
```

### 3. Cài đặt thư viện

```powershell
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường

Sao chép `.env.example` thành `.env`:

```powershell
copy .env.example .env
```

Sau đó điền API key:

```dotenv
PORT=3000
GEMINI_API_KEY=your_gemini_api_key
```

Không commit file `.env` hoặc bất kỳ thông tin xác thực nào lên GitHub.

### 5. Khởi chạy

Cách đơn giản nhất trên Windows:

```bat
start.bat
```

Hoặc chạy trực tiếp:

```powershell
python main.py
```

Ứng dụng FastAPI mặc định chạy tại:

- http://127.0.0.1:8000
- Tài liệu API: http://127.0.0.1:8000/docs

`start.bat` sẽ tạo virtual environment nếu chưa có, khởi chạy Uvicorn, tạo thư mục profile/log và tùy chọn mở profile Ungoogled Chromium.

## Chạy bằng Node.js/Express

Repository cũng chứa phiên bản server Express trong `server.js`.

```powershell
npm install
npm start
```

Hoặc chạy ở chế độ phát triển:

```powershell
npm run dev
```

Server Express sử dụng cổng được khai báo trong `PORT`, mặc định là `3000`, và truy cập tại http://127.0.0.1:3000.

## Cấu trúc thư mục

```text
.
├── app/                  # Module FastAPI, model, router và template
├── public/               # Tài nguyên tĩnh cho phiên bản Express
├── views/                # Template EJS
├── main.py               # Điểm khởi chạy FastAPI
├── server.js             # Server Express thay thế
├── db.js                 # Lớp dữ liệu cho phiên bản Node.js
├── ai_service.js         # Tích hợp Gemini cho Node.js
├── fb_service.js         # Các tác vụ liên quan đến Facebook
├── requirements.txt      # Dependency Python
├── package.json          # Dependency và script Node.js
├── .env.example          # Mẫu cấu hình môi trường
├── start.bat             # Script khởi chạy trên Windows
└── push.bat              # Script hỗ trợ thao tác Git trên Windows
```

## Các đường dẫn chính

| Chức năng | URL FastAPI | URL Express |
|---|---|---|
| Dashboard | `/` | `/` |
| Tin bất động sản | `/listings` | `/listings` |
| Tài khoản Facebook | `/facebook/accounts` | `/facebook/accounts` |
| Nhóm Facebook | `/facebook/groups` | `/facebook/groups` |
| Lịch sử đăng bài | `/facebook/logs` | `/facebook/logs` |
| Cài đặt | `/settings` | `/settings` |

## Bảo mật và vận hành

- Không chia sẻ `GEMINI_API_KEY`, cookie Facebook, access token hoặc thư mục `profiles/`.
- Nên chạy ứng dụng trên `127.0.0.1` khi chỉ sử dụng trên máy cá nhân.
- Sao lưu dữ liệu trước khi xóa hàng loạt hoặc reset dữ liệu mẫu.
- Kiểm tra quyền đăng bài và quy định của từng nhóm trước khi sử dụng chức năng đăng tự động.
- Không dùng tài khoản cá nhân chính cho thử nghiệm tự động hóa.

## Xử lý sự cố

- **Không mở được server:** kiểm tra Python, chạy `pip install -r requirements.txt` và xem `logs/start_debug.log`.
- **Không tìm thấy Chromium:** cài Ungoogled Chromium hoặc tiếp tục sử dụng trình duyệt mặc định.
- **AI không hoạt động:** kiểm tra `GEMINI_API_KEY`, kết nối mạng và model/API quota.
- **Cổng đã được sử dụng:** đổi cổng khi chạy Uvicorn hoặc cập nhật `PORT` khi chạy Express.

## Đóng góp

1. Tạo một fork của repository.
2. Tạo branch cho thay đổi của bạn.
3. Kiểm thử local trước khi commit.
4. Mở pull request với mô tả rõ ràng về thay đổi.

## Giấy phép

Repository hiện chưa khai báo giấy phép. Vui lòng liên hệ chủ repository trước khi sử dụng trong sản phẩm thương mại hoặc phân phối lại.
