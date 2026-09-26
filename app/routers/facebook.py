from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Group, Content
import browser_cookie3

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

router = APIRouter(tags=["Facebook Management"])
templates = Jinja2Templates(directory="app/templates")

def debug_green(message):
    print(f"\033[92m[DEBUG] {message}\033[0m")

# --- HÀM HỖ TRỢ QUY ĐỔI SỐ THÀNH VIÊN ĐỂ SẮP XẾP ---
def parse_member_count(val):
    if not val or val in ["MEM", "N/A"]:
        return -1
    try:
        val_str = str(val).upper().replace(',', '.').strip()
        if val_str.endswith('K'):
            return float(val_str[:-1]) * 1000
        elif val_str.endswith('M'):
            return float(val_str[:-1]) * 1000000
        return float(val_str)
    except Exception:
        return -1

# --- QUẢN LÝ ACCOUNTS ---
@router.get("/accounts")
def list_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    return templates.TemplateResponse(request=request, name="accounts.html", context={"accounts": accounts})

@router.post("/accounts")
def create_account(
    name: str = Form(...),
    email: str = Form(...),
    cookie: str = Form(None),
    status: str = Form("Hoạt động"),
    db: Session = Depends(get_db)
):
    new_acc = Account(name=name, email=email, cookie=cookie, status=status)
    db.add(new_acc)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=303)

@router.post("/accounts/{account_id}/delete")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc:
        db.delete(acc)
        db.commit()
    return RedirectResponse(url="/accounts", status_code=303)

@router.get("/accounts/get-cookie")
def get_chrome_facebook_cookie():
    try:
        debug_green("Đang quét Cookie Facebook từ trình duyệt...")
        cj = browser_cookie3.chrome(domain_name='.facebook.com')
        cookie_dict = {c.name: c.value for c in cj}
        
        if "c_user" in cookie_dict and "xs" in cookie_dict:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            uid = cookie_dict.get("c_user")
            return JSONResponse({"success": True, "cookie": cookie_str, "uid": uid})
        else:
            return JSONResponse({"success": False, "message": "Chưa đăng nhập FB trên trình duyệt!"})
    except Exception as e:
        return JSONResponse({"success": False, "message": f"Không lấy được cookie: {str(e)}"})

# --- QUẢN LÝ GROUPS (ĐÃ SẮP XẾP NHIỀU MEM LÊN ĐẦU) ---
@router.get("/groups")
def list_groups(request: Request, db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    # Sắp xếp danh sách nhóm giảm dần theo số thành viên
    groups.sort(key=lambda g: parse_member_count(g.member_count), reverse=True)
    return templates.TemplateResponse(request=request, name="groups.html", context={"groups": groups})

# --- API QUÉT LẤY DANH SÁCH NHÓM ---
@router.post("/groups/scan")
def scan_groups(clear_all: bool = False, db: Session = Depends(get_db)):
    driver = None
    original_window = None
    scan_tab = None
    
    try:
        if clear_all:
            debug_green("Đang xóa dữ liệu nhóm cũ trong CSDL...")
            db.query(Group).delete()
            db.commit()

        debug_green("Kết nối trình duyệt cổng 9222...")
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        try:
            service = Service(ChromeDriverManager(driver_version="138.0.7204.303").install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            driver = webdriver.Chrome(options=chrome_options)

        driver.set_script_timeout(180)
        
        original_window = driver.current_window_handle
        driver.switch_to.new_window('tab')
        scan_tab = driver.current_window_handle
        
        debug_green("Mở trang danh sách nhóm đã tham gia...")
        driver.get("https://www.facebook.com/groups/joins/")
        time.sleep(3)
        
        debug_green("Đang cuộn tự động để tải toàn bộ danh sách nhóm...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        same_count = 0
        
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                same_count += 1
                if same_count >= 3:
                    break
            else:
                last_height = new_height
                same_count = 0

        debug_green("Đang bóc tách danh sách nhóm...")
        groups_data = driver.execute_script("""
            let groups = [];
            let seenUrls = new Set();
            let anchors = document.querySelectorAll('a[href*="/groups/"]');
            
            anchors.forEach(a => {
                let href = a.href;
                if (!href || href.includes('/feed/') || href.includes('/create/') || href.includes('/category/') || href.includes('/discover/') || href.includes('/joins')) return;
                
                let parts = href.split('?')[0].split('/');
                if (!parts.includes('groups')) return;
                let groupIdx = parts.indexOf('groups');
                if (parts.length <= groupIdx + 1 || !parts[groupIdx + 1]) return;
                let cleanUrl = "https://www.facebook.com/groups/" + parts[groupIdx + 1];

                if (seenUrls.has(cleanUrl)) return;

                let rawName = a.innerText.trim();
                if (!rawName || rawName === "Xem nhóm" || rawName === "Tham gia" || rawName.length < 2) return;

                let cleanName = rawName.split("\\n")[0].split("Lần truy cập")[0].split("Lần hoạt động")[0].trim();

                seenUrls.add(cleanUrl);
                groups.push({
                    name: cleanName,
                    url: cleanUrl,
                    members: "MEM"
                });
            });
            return groups;
        """)
        
        count = 0
        for item in groups_data:
            clean_url = item['url']
            group_name = item['name']
            
            try:
                existing = db.query(Group).filter(Group.url == clean_url).first()
                if not existing:
                    new_group = Group(
                        group_name=group_name, 
                        url=clean_url, 
                        category="Mặc định",
                        member_count="MEM"
                    )
                    db.add(new_group)
                    db.commit()
                    count += 1
                else:
                    existing.group_name = group_name
                    if not existing.member_count or existing.member_count == "N/A":
                        existing.member_count = "MEM"
                    db.commit()
            except Exception:
                db.rollback()
                continue
        
        msg = f"Đã xóa dữ liệu cũ và quét thành công {count} nhóm!" if clear_all else f"Quét thành công và cập nhật {count} nhóm!"
        debug_green(msg)
        return JSONResponse({"success": True, "message": msg})
        
    except Exception as e:
        debug_green(f"Lỗi quét nhóm: {str(e)}")
        return JSONResponse({"success": False, "message": f"Lỗi quét nhóm: {str(e)}"})
        
    finally:
        if driver:
            try:
                if scan_tab and scan_tab in driver.window_handles and len(driver.window_handles) > 1:
                    driver.switch_to.window(scan_tab)
                    driver.close()
                if original_window and original_window in driver.window_handles:
                    driver.switch_to.window(original_window)
            except Exception:
                pass

# --- API LẤY SỐ THÀNH VIÊN BẰNG TAB NGẦM TỰ ĐỘNG ---
@router.post("/groups/{group_id}/fetch-members")
def fetch_single_group_members(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        return JSONResponse({"success": False, "message": "Không tìm thấy nhóm"}, status_code=404)
    
    driver = None
    main_handle = None
    bg_handle = None
    
    try:
        debug_green(f"Đang mở TAB NGẦM bóc tách thành viên nhóm: {group.group_name}")
        
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        try:
            service = Service(ChromeDriverManager(driver_version="138.0.7204.303").install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            driver = webdriver.Chrome(options=chrome_options)

        main_handle = driver.current_window_handle
        handles_before = set(driver.window_handles)
        
        driver.execute_cdp_cmd('Target.createTarget', {
            'url': group.url,
            'background': True
        })
        
        time.sleep(2.5)
        
        handles_after = set(driver.window_handles)
        new_handles = list(handles_after - handles_before)
        
        member_count = None
        
        if new_handles:
            bg_handle = new_handles[0]
            driver.switch_to.window(bg_handle)
            
            member_count = driver.execute_script("""
                let text = document.body ? document.body.innerText : '';
                let match = text.match(/([\\d\\.,]+\\s*[kKMm]?)\\s*(?:thành viên|members)/i);
                if (match) {
                    return match[1].replace(/\\s+/g, '').toUpperCase();
                }
                
                let html = document.documentElement ? document.documentElement.innerHTML : '';
                let matchJson = html.match(/"member_count":\\s*(\\d+)/);
                if (!matchJson) matchJson = html.match(/"group_total_members":\\s*(\\d+)/);
                if (!matchJson) matchJson = html.match(/"text"\\s*:\\s*"([\\d\\.,]+\\s*[kKMm]?)\\s*(?:thành viên|members)"/i);
                
                if (matchJson) {
                    if (typeof matchJson[1] === 'string' && matchJson[1].match(/[kKMm]/)) {
                        return matchJson[1].replace(/\\s+/g, '').toUpperCase();
                    }
                    let count = parseInt(matchJson[1]);
                    return count >= 1000 ? (count / 1000).toFixed(1) + 'K' : count.toString();
                }
                return null;
            """)
        
        if member_count:
            group.member_count = member_count
            db.commit()
            debug_green(f"Lấy thành công: {member_count}")
            return JSONResponse({"success": True, "members": member_count})
        else:
            return JSONResponse({"success": False, "message": "Không quét được số thành viên."})
            
    except Exception as e:
        debug_green(f"Lỗi tab ngầm: {str(e)}")
        return JSONResponse({"success": False, "message": f"Lỗi: {str(e)}"})
        
    finally:
        if driver:
            try:
                if bg_handle and bg_handle in driver.window_handles:
                    driver.switch_to.window(bg_handle)
                    driver.close()
                if main_handle and main_handle in driver.window_handles:
                    driver.switch_to.window(main_handle)
            except Exception:
                pass

@router.get("/content-library")
def list_contents(request: Request, db: Session = Depends(get_db)):
    contents = db.query(Content).order_by(Content.id.desc()).all()
    return templates.TemplateResponse(request=request, name="content_library.html", context={"contents": contents})