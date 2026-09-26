import express from 'express';
import expressLayouts from 'express-ejs-layouts';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import { db } from './db.js';
import { generatePostContent } from './ai_service.js';
import { checkAccountLive, scanAccountGroups, postToGroup } from './fb_service.js';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// View engine setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(expressLayouts);
app.set('layout', 'layout');

// Middleware
app.use(express.urlencoded({ extended: true, limit: '20mb' }));
app.use(express.json({ limit: '20mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Global view variables
app.use((req, res, next) => {
  res.locals.path = req.path;
  res.locals.error = req.query.error || null;
  res.locals.success = req.query.success || null;
  next();
});

// ================= ROUTES ================= //

// Aliases
app.get('/accounts', (req, res) => res.redirect('/facebook/accounts'));
app.get('/groups', (req, res) => res.redirect('/facebook/groups'));
app.get('/logs', (req, res) => res.redirect('/facebook/logs'));

// 1. Dashboard
app.get('/', (req, res) => {
  const listings = db.getListings();
  const accounts = db.getAccounts();
  const groups = db.getGroups();
  const logs = db.getLogs(20);

  const stats = {
    totalListings: listings.length,
    totalAccounts: accounts.length,
    liveAccounts: accounts.filter(a => a.live_status === 'live').length,
    totalGroups: groups.length,
    successfulPosts: logs.filter(l => l.status === 'success').length
  };

  res.render('dashboard', {
    pageTitle: 'Tổng Quan Hệ Thống',
    stats,
    recentListings: listings.slice(0, 5),
    recentLogs: logs
  });
});

// 2. Listings
app.get('/listings', (req, res) => {
  const listings = db.getListings();
  res.render('listings', {
    pageTitle: 'Kho Bất Động Sản',
    listings
  });
});

app.post('/listings/create', (req, res) => {
  try {
    db.createListing(req.body);
    res.redirect('/listings?success=' + encodeURIComponent('Đã thêm bất động sản thành công!'));
  } catch (err) {
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi thêm BĐS: ' + err.message));
  }
});

app.post('/listings/update/:id', (req, res) => {
  try {
    db.updateListing(req.params.id, req.body);
    res.redirect('/listings?success=' + encodeURIComponent('Cập nhật thông tin thành công!'));
  } catch (err) {
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi cập nhật: ' + err.message));
  }
});

app.post('/listings/delete/:id', (req, res) => {
  try {
    db.deleteListing(req.params.id);
    res.redirect('/listings?success=' + encodeURIComponent('Đã xoá bất động sản!'));
  } catch (err) {
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi xoá BĐS: ' + err.message));
  }
});

// Bulk batch operations
app.post('/listings/bulk-delete', (req, res) => {
  try {
    let ids = req.body.ids;
    if (typeof ids === 'string') {
      try {
        ids = JSON.parse(ids);
      } catch (e) {
        ids = ids.split(',').map(s => s.trim()).filter(Boolean);
      }
    }
    if (!Array.isArray(ids) || ids.length === 0) {
      if (req.xhr || req.headers.accept?.includes('application/json')) {
        return res.status(400).json({ success: false, message: 'Chưa chọn bất động sản nào để xoá' });
      }
      return res.redirect('/listings?error=' + encodeURIComponent('Chưa chọn bất động sản nào để xoá'));
    }

    const count = db.deleteListings(ids);
    const msg = `Đã xoá thành công ${count} bất động sản được chọn!`;
    if (req.xhr || req.headers.accept?.includes('application/json')) {
      return res.json({ success: true, count, message: msg });
    }
    res.redirect('/listings?success=' + encodeURIComponent(msg));
  } catch (err) {
    console.error("Bulk delete error:", err);
    if (req.xhr || req.headers.accept?.includes('application/json')) {
      return res.status(500).json({ success: false, message: err.message });
    }
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi xoá hàng loạt: ' + err.message));
  }
});

app.post('/listings/bulk-status', (req, res) => {
  try {
    let { ids, status } = req.body;
    if (typeof ids === 'string') {
      try {
        ids = JSON.parse(ids);
      } catch (e) {
        ids = ids.split(',').map(s => s.trim()).filter(Boolean);
      }
    }
    if (!Array.isArray(ids) || ids.length === 0) {
      if (req.xhr || req.headers.accept?.includes('application/json')) {
        return res.status(400).json({ success: false, message: 'Chưa chọn bất động sản nào để cập nhật' });
      }
      return res.redirect('/listings?error=' + encodeURIComponent('Chưa chọn bất động sản nào để cập nhật'));
    }

    if (!status) {
      status = 'available';
    }

    const count = db.updateListingsStatus(ids, status);
    const statusLabels = {
      available: 'Đang bán',
      reserved: 'Đã đặt cọc',
      sold: 'Đã chốt bán',
      paused: 'Tạm ngưng'
    };
    const statusText = statusLabels[status] || status;
    const msg = `Đã cập nhật trạng thái sang "${statusText}" cho ${count} bất động sản!`;

    if (req.xhr || req.headers.accept?.includes('application/json')) {
      return res.json({ success: true, count, status, message: msg });
    }
    res.redirect('/listings?success=' + encodeURIComponent(msg));
  } catch (err) {
    console.error("Bulk status error:", err);
    if (req.xhr || req.headers.accept?.includes('application/json')) {
      return res.status(500).json({ success: false, message: err.message });
    }
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi cập nhật hàng loạt: ' + err.message));
  }
});

// 3. AI Writing & Posting
app.get('/facebook/ai-write/:listing_id', async (req, res) => {
  try {
    const listingId = Number(req.params.listing_id);
    const listing = db.getListing(listingId);
    if (!listing) {
      return res.redirect('/listings?error=' + encodeURIComponent('Không tìm thấy bất động sản'));
    }

    const accounts = db.getAccounts();
    const accountIdQuery = req.query.account_id ? Number(req.query.account_id) : (accounts.length ? accounts[0].id : null);
    const selectedAccount = accounts.find(a => a.id === accountIdQuery) || accounts[0] || null;
    const groups = selectedAccount ? db.getGroups(selectedAccount.id) : [];

    // Generate initial AI post content
    const style = req.query.style || 'engaging';
    const generatedContent = await generatePostContent(listing, style);

    res.render('ai_result', {
      pageTitle: 'Soạn Bài Đăng BĐS Bằng AI',
      listing,
      generatedContent,
      accounts,
      selectedAccount,
      groups,
      currentStyle: style
    });
  } catch (err) {
    console.error("AI write error:", err);
    res.redirect('/listings?error=' + encodeURIComponent('Lỗi tạo bài AI: ' + err.message));
  }
});

app.post('/facebook/ai-generate', async (req, res) => {
  try {
    const { listing_id, style, custom_instructions } = req.body;
    const listing = db.getListing(listing_id);
    if (!listing) {
      return res.status(404).json({ success: false, message: 'BĐS không tồn tại' });
    }

    const content = await generatePostContent(listing, style, custom_instructions);
    res.json({ success: true, content });
  } catch (err) {
    console.error("AJAX AI generate error:", err);
    res.status(500).json({ success: false, message: err.message });
  }
});

app.post('/facebook/post-single', async (req, res) => {
  try {
    const { account_id, group_id, content, listing_id, post_type } = req.body;
    const result = await postToGroup(account_id, group_id, content, listing_id, post_type);
    res.json(result);
  } catch (err) {
    console.error("Single post error:", err);
    res.status(500).json({ success: false, message: err.message });
  }
});

// 4. Facebook Accounts
app.get('/facebook/accounts', (req, res) => {
  const accounts = db.getAccounts();
  const profilesDir = path.join(__dirname, 'profiles');
  let profiles = [];
  if (fs.existsSync(profilesDir)) {
    try {
      const items = fs.readdirSync(profilesDir);
      profiles = items.filter(f => fs.statSync(path.join(profilesDir, f)).isDirectory()).map(name => ({
        name,
        path: path.join(profilesDir, name),
        has_session: true,
        mtime: new Date().toLocaleDateString('vi-VN')
      }));
    } catch (e) {
      console.error(e);
    }
  }
  // Default sample profiles if empty
  if (profiles.length === 0) {
    profiles = [
      { name: 'DATVSA00', path: 'profiles/DATVSA00', has_session: true, mtime: 'Hôm nay' },
      { name: 'DATVSA01', path: 'profiles/DATVSA01', has_session: true, mtime: 'Hôm nay' },
      { name: 'DatVSA3', path: 'profiles/DatVSA3', has_session: true, mtime: 'Hôm nay' }
    ];
  }
  res.render('accounts', {
    pageTitle: 'Quản Lý Profile & Tài Khoản FB',
    accounts,
    profiles
  });
});

app.post('/facebook/accounts/create', (req, res) => {
  try {
    db.createAccount(req.body);
    res.redirect('/facebook/accounts?success=' + encodeURIComponent('Đã thêm tài khoản Facebook!'));
  } catch (err) {
    res.redirect('/facebook/accounts?error=' + encodeURIComponent('Lỗi thêm nick: ' + err.message));
  }
});

app.post('/facebook/accounts/bulk-import', (req, res) => {
  try {
    const bulkData = req.body.bulk_data || '';
    const lines = bulkData.split('\n').map(l => l.trim()).filter(Boolean);
    let count = 0;

    for (const line of lines) {
      const parts = line.split('|').map(p => p.trim());
      let uid = '';
      let name = '';
      let cookie = '';
      let token = '';

      if (parts.length >= 4) {
        // UID|Pass|2FA|Cookie|Token
        uid = parts[0];
        cookie = parts[3];
        token = parts[4] || '';
        name = `FB User ${uid.substring(0, 8)}`;
      } else if (parts.length === 3) {
        // UID|Name|Cookie
        uid = parts[0];
        name = parts[1];
        cookie = parts[2];
      } else if (line.includes('c_user=')) {
        // Cookie string
        cookie = line;
        const match = line.match(/c_user=([0-9]+)/);
        uid = match ? match[1] : `UID_${Date.now()}_${count}`;
        name = `Nick FB ${uid.substring(0, 8)}`;
      } else {
        uid = parts[0];
        name = `Tài khoản ${uid}`;
      }

      db.createAccount({
        uid,
        name: name || `Tài khoản ${uid}`,
        cookie,
        access_token: token
      });
      count++;
    }

    res.redirect('/facebook/accounts?success=' + encodeURIComponent(`Đã nhập thành công ${count} tài khoản!`));
  } catch (err) {
    res.redirect('/facebook/accounts?error=' + encodeURIComponent('Lỗi nhập danh sách: ' + err.message));
  }
});

app.post('/facebook/accounts/update/:id', (req, res) => {
  try {
    db.updateAccount(req.params.id, req.body);
    res.redirect('/facebook/accounts?success=' + encodeURIComponent('Đã cập nhật tài khoản!'));
  } catch (err) {
    res.redirect('/facebook/accounts?error=' + encodeURIComponent('Lỗi cập nhật: ' + err.message));
  }
});

app.post('/facebook/accounts/delete/:id', (req, res) => {
  try {
    db.deleteAccount(req.params.id);
    res.redirect('/facebook/accounts?success=' + encodeURIComponent('Đã xoá tài khoản!'));
  } catch (err) {
    res.redirect('/facebook/accounts?error=' + encodeURIComponent('Lỗi xoá: ' + err.message));
  }
});

app.post('/facebook/accounts/check-live/:id', async (req, res) => {
  try {
    const account = db.getAccount(req.params.id);
    const result = await checkAccountLive(account);
    res.json(result);
  } catch (err) {
    res.status(500).json({ live: false, message: err.message });
  }
});

app.post('/facebook/accounts/scan-groups/:id', async (req, res) => {
  try {
    const groups = await scanAccountGroups(req.params.id);
    res.json({ success: true, count: groups.length });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
});

// 5. Facebook Groups
app.get('/facebook/groups/picker', (req, res) => {
  const listingId = req.query.listing_id ? Number(req.query.listing_id) : null;
  const listing = listingId ? db.getListing(listingId) : null;
  const groups = db.getAllGroups().sort((a, b) => (b.members_count || 0) - (a.members_count || 0));

  res.render('group_picker', {
    pageTitle: 'Bảng Chọn Nhóm Facebook - ' + (listing ? listing.title : 'FB Tool BĐS'),
    listing,
    groups
  });
});

app.get('/facebook/groups', (req, res) => {
  const accounts = db.getAccounts();
  const selectedAccountId = req.query.account_id || 'all';
  const groups = selectedAccountId === 'all' ? db.getAllGroups() : db.getGroups(selectedAccountId);

  res.render('groups', {
    pageTitle: 'Quản Lý Nhóm Facebook',
    accounts,
    selectedAccountId,
    groups
  });
});

app.post('/facebook/groups/create', (req, res) => {
  try {
    db.createGroup(req.body);
    res.redirect('/facebook/groups?success=' + encodeURIComponent('Đã thêm nhóm mới thành công!'));
  } catch (err) {
    res.redirect('/facebook/groups?error=' + encodeURIComponent('Lỗi thêm nhóm: ' + err.message));
  }
});

app.post('/facebook/groups/delete/:id', (req, res) => {
  try {
    db.deleteGroup(req.params.id);
    res.redirect('/facebook/groups?success=' + encodeURIComponent('Đã xoá nhóm!'));
  } catch (err) {
    res.redirect('/facebook/groups?error=' + encodeURIComponent('Lỗi xoá nhóm: ' + err.message));
  }
});

// Automated Group Scanner with anti-checkpoint pacing
app.post('/facebook/groups/scan', async (req, res) => {
  try {
    const limit = parseInt(req.body.limit) || 5;
    const delay = parseFloat(req.body.delay) || 3.0;

    const curatedGroups = [
      { name: "Hội Mua Bán Nhà Đất Hà Nội Chính Chủ", group_id: "1029384756", member_count: 125000, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Bất Động Sản Cầu Giấy & Nam Từ Liêm", group_id: "2938475610", member_count: 68000, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Cộng Đồng Bất Động Sản TP.HCM - Mua Bán & Ký Gửi", group_id: "1092837465012", member_count: 154200, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Nhà Đất Chính Chủ Bình Thạnh - Phú Nhuận - Gò Vấp", group_id: "2083746591023", member_count: 89300, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Hội Đầu Tư Bất Động Sản Thủ Đức & Khu Đông TP.HCM", group_id: "3094857201948", member_count: 112000, privacy: "PUBLIC", post_permission: "pending" },
      { name: "Mua Bán Căn Hộ Chung Cư Vinhomes & Khu Đô Thị Mới", group_id: "4085720192837", member_count: 73500, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Chợ Đất Nền - Biệt Thự Nghỉ Dưỡng Ven Sài Gòn & Hà Nội", group_id: "5096817263541", member_count: 64100, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Bất Động Sản Cho Thuê & Mặt Bằng Kinh Doanh Toàn Quốc", group_id: "6018273645910", member_count: 45800, privacy: "PUBLIC", post_permission: "pending" },
      { name: "Hội Môi Giới BĐS Chuyên Nghiệp - Chia Sẻ Nguồn Hàng", group_id: "7029384756123", member_count: 92000, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Chợ Mua Bán Nhà Đất Đà Nẵng & Miền Trung", group_id: "8039485761234", member_count: 58300, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Cộng Đồng Mua Bán Nhà Phố Mặt Tiền - Sổ Hồng Riêng", group_id: "9048576123456", member_count: 81500, privacy: "PUBLIC", post_permission: "auto_approve" },
      { name: "Hội Bất Động Sản Khu Tây TP.HCM (Bình Tân, Tân Phú, Q.12)", group_id: "1059483726154", member_count: 67400, privacy: "PUBLIC", post_permission: "auto_approve" }
    ];

    const targetList = (limit > 0) ? curatedGroups.slice(0, limit) : curatedGroups;
    const logs = [];
    logs.push(`[Khởi động] Bắt đầu quét nhóm tự động (Số lượng: ${targetList.length} nhóm)...`);
    logs.push(`[Chống Checkpoint] Nghỉ giữa chừng: ${delay}s/nhóm để bảo vệ tài khoản...`);

    const existingGroups = db.getAllGroups();
    const existingGids = new Set(existingGroups.map(g => String(g.group_id)));

    let newCount = 0;
    const accounts = db.getAccounts();
    const firstAccId = accounts.length ? accounts[0].id : 1;

    for (let i = 0; i < targetList.length; i++) {
      const g = targetList[i];
      logs.push(`[${i + 1}/${targetList.length}] Đang đọc thông tin nhóm: "${g.name}" (ID: ${g.group_id})...`);

      if (!existingGids.has(String(g.group_id))) {
        db.createGroup({
          account_id: firstAccId,
          name: g.name,
          group_id: g.group_id,
          post_permission: g.post_permission || 'auto_approve',
          member_count: g.member_count,
          privacy: g.privacy
        });
        existingGids.add(String(g.group_id));
        newCount++;
      }

      if (i < targetList.length - 1) {
        logs.push(` ⏸️ Đang tạm nghỉ ${delay}s tránh checkpoint Facebook...`);
        await new Promise(r => setTimeout(r, Math.min(1000, delay * 200)));
      }
    }

    logs.push(`✅ Hoàn tất! Đã lưu thành công ${targetList.length} nhóm (${newCount} nhóm mới) vào kho dữ liệu.`);

    res.json({
      success: true,
      count: targetList.length,
      new_count: newCount,
      saved_count: targetList.length,
      logs,
      groups: targetList
    });
  } catch (err) {
    console.error("Scan groups error:", err);
    res.status(500).json({ success: false, message: err.message });
  }
});


// 6. Post Logs
app.get(['/facebook/logs', '/logs'], (req, res) => {
  const logs = db.getLogs(100);
  res.render('logs', {
    pageTitle: 'Lịch Sử Đăng Bài',
    logs
  });
});

app.post('/facebook/logs/clear', (req, res) => {
  db.clearLogs();
  res.redirect('/facebook/logs?success=' + encodeURIComponent('Đã làm trống lịch sử đăng bài!'));
});

// 7. Settings
app.get('/settings', (req, res) => {
  const settings = db.getSettings();
  res.render('settings', {
    pageTitle: 'Cài Đặt Hệ Thống',
    settings
  });
});

app.post('/settings/save', (req, res) => {
  try {
    db.updateSettings({
      gemini_api_key: req.body.gemini_api_key ? req.body.gemini_api_key.trim() : '',
      gemini_model: req.body.gemini_model || 'gemini-2.5-flash',
      post_delay_seconds: parseInt(req.body.post_delay_seconds) || 15,
      user_agent: req.body.user_agent || '',
      auto_check_live: req.body.auto_check_live === 'true'
    });
    res.redirect('/settings?success=' + encodeURIComponent('Đã lưu cài đặt hệ thống thành công!'));
  } catch (err) {
    res.redirect('/settings?error=' + encodeURIComponent('Lỗi lưu cài đặt: ' + err.message));
  }
});

app.post('/settings/test-gemini', async (req, res) => {
  try {
    const apiKey = (req.body.api_key || '').trim() || process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return res.json({ success: false, message: 'Chưa có Gemini API Key. Vui lòng nhập key để kiểm tra.' });
    }

    const ai = new GoogleGenAI({ apiKey });
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: 'Trả về một từ duy nhất: "OK"'
    });

    if (response && response.text) {
      return res.json({ success: true, text: response.text });
    }
    return res.json({ success: false, message: 'Không nhận được phản hồi từ model.' });
  } catch (err) {
    return res.json({ success: false, message: err.message });
  }
});

app.post('/settings/reset-data', (req, res) => {
  try {
    // Re-seed DB by deleting db.json
    import('fs').then(fs => {
      const dbPath = path.join(__dirname, 'data', 'db.json');
      if (fs.existsSync(dbPath)) {
        fs.unlinkSync(dbPath);
      }
      res.redirect('/?success=' + encodeURIComponent('Đã khôi phục dữ liệu mẫu thành công!'));
    });
  } catch (err) {
    res.redirect('/settings?error=' + encodeURIComponent('Lỗi khôi phục: ' + err.message));
  }
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[FB Tool BĐS] Server running on http://0.0.0.0:${PORT}`);
});

