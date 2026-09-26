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
  res.render('accounts', {
    pageTitle: 'Quản Lý Tài Khoản Facebook',
    accounts
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

