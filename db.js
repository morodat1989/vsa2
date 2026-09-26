import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.join(__dirname, 'data');
const DB_FILE = path.join(DATA_DIR, 'db.json');

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const defaultData = {
  listings: [
    {
      id: 1,
      title: "Bán nhà phố mặt tiền Quận Bình Thạnh - 4 tầng hiện đại",
      address: "125/45 Đinh Bộ Lĩnh, Phường 26, Quận Bình Thạnh, TP.HCM",
      price: 8.5, // Tỷ VNĐ
      area: 85, // m2
      bedrooms: 4,
      bathrooms: 4,
      direction: "Đông Nam",
      legal: "Sổ hồng riêng, hoàn công đầy đủ",
      interior: "Full nội thất cao cấp nhập khẩu",
      contact_name: "Nguyễn Văn Hùng",
      contact_phone: "0908123456",
      images: "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=600&auto=format&fit=crop&q=80",
      description: "Nhà mới xây xong, đường trước nhà 6m xe hơi quay đầu thoải mái. Khu dân cư văn minh, an ninh 24/7, gần chợ Bà Chiểu, Landmark 81 chỉ 5 phút.",
      status: "available",
      created_at: new Date(Date.now() - 86400000 * 2).toISOString()
    },
    {
      id: 2,
      title: "Căn hộ cao cấp Vinhomes Grand Park 2PN view công viên",
      address: "Phân khu Rainbow, Vinhomes Grand Park, TP. Thủ Đức",
      price: 2.85,
      area: 68,
      bedrooms: 2,
      bathrooms: 2,
      direction: "Nam",
      legal: "Hợp đồng mua bán, đang chờ cấp sổ",
      interior: "Nội thất cơ bản chủ đầu tư",
      contact_name: "Trần Mai Anh",
      contact_phone: "0912345678",
      images: "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=600&auto=format&fit=crop&q=80",
      description: "Căn hộ tầng trung thoáng mát, ban công nhìn trọn đại công viên 36ha. Tiện ích hồ bơi, trường Vinschool, TTTM Vincom Mega Mall ngay chân tòa nhà.",
      status: "available",
      created_at: new Date(Date.now() - 86400000).toISOString()
    },
    {
      id: 3,
      title: "Đất nền thổ cư KDC Nam Long Cần Thơ - Sổ đỏ cầm tay",
      address: "Đường số 5, KDC Nam Long, Cái Răng, TP. Cần Thơ",
      price: 3.2,
      area: 110,
      bedrooms: 0,
      bathrooms: 0,
      direction: "Bắc",
      legal: "Sổ đỏ trao tay, công chứng trong ngày",
      interior: "Đất trống, xây tự do",
      contact_name: "Lê Quốc Bảo",
      contact_phone: "0977889900",
      images: "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600&auto=format&fit=crop&q=80",
      description: "Vị trí đắc địa, đối diện công viên hồ sinh thái, cơ sở hạ tầng điện nước âm hoàn chỉnh, vỉa hè 3m cây xanh rợp bóng mát.",
      status: "available",
      created_at: new Date().toISOString()
    }
  ],
  accounts: [
    {
      id: 1,
      uid: "100088923412345",
      name: "Nguyễn Tuấn BĐS Sài Gòn",
      cookie: "c_user=100088923412345; xs=42%3Av9412...; datr=abc123xyz;",
      access_token: "EAABsbCS1iHg...MOCK_TOKEN_TUAN",
      user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
      proxy: "",
      status: "active",
      live_status: "live",
      groups_count: 5,
      last_check: new Date().toISOString(),
      created_at: new Date().toISOString()
    },
    {
      id: 2,
      uid: "100091238475812",
      name: "Hoàng BĐS Đầu Tư & Cho Thuê",
      cookie: "c_user=100091238475812; xs=28%3Aq9811...;",
      access_token: "EAABsbCS1iHg...MOCK_TOKEN_HOANG",
      user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
      proxy: "",
      status: "active",
      live_status: "live",
      groups_count: 3,
      last_check: new Date().toISOString(),
      created_at: new Date().toISOString()
    }
  ],
  groups: [
    {
      id: 1,
      account_id: 1,
      group_id: "192837465012",
      name: "CỘNG ĐỒNG BẤT ĐỘNG SẢN TP.HCM - MUA BÁN & KÝ GỬI",
      privacy: "PUBLIC",
      member_count: 145000,
      post_permission: "auto_approve",
      joined: true,
      created_at: new Date().toISOString()
    },
    {
      id: 2,
      account_id: 1,
      group_id: "283746591023",
      name: "NHÀ ĐẤT CHÍNH CHỦ BÌNH THẠNH - PHÚ NHUẬN",
      privacy: "PUBLIC",
      member_count: 82000,
      post_permission: "auto_approve",
      joined: true,
      created_at: new Date().toISOString()
    },
    {
      id: 3,
      account_id: 1,
      group_id: "394857201948",
      name: "HỘI ĐẦU TƯ BẤT ĐỘNG SẢN VEN SÔNG & THỦ ĐỨC",
      privacy: "CLOSED",
      member_count: 98000,
      post_permission: "pending",
      joined: true,
      created_at: new Date().toISOString()
    },
    {
      id: 4,
      account_id: 2,
      group_id: "485720192837",
      name: "MUA BÁN CĂN HỘ CHUNG CƯ VINHOMES GRAND PARK",
      privacy: "PUBLIC",
      member_count: 65000,
      post_permission: "auto_approve",
      joined: true,
      created_at: new Date().toISOString()
    },
    {
      id: 5,
      account_id: 2,
      group_id: "596817263541",
      name: "BẤT ĐỘNG SẢN MIỀN TÂY - CẦN THƠ - VĨNH LONG",
      privacy: "PUBLIC",
      member_count: 52000,
      post_permission: "auto_approve",
      joined: true,
      created_at: new Date().toISOString()
    }
  ],
  logs: [
    {
      id: 1,
      account_id: 1,
      account_name: "Nguyễn Tuấn BĐS Sài Gòn",
      group_id: "192837465012",
      group_name: "CỘNG ĐỒNG BẤT ĐỘNG SẢN TP.HCM - MUA BÁN & KÝ GỬI",
      listing_id: 1,
      listing_title: "Bán nhà phố mặt tiền Quận Bình Thạnh - 4 tầng hiện đại",
      post_type: "text_with_images",
      content: "🔥 SIÊU PHẨM MẶT TIỀN BÌNH THẠNH - GIÁ CHỈ 8.5 TỶ TL 🔥\nNhà 4 tầng mới keng, đường 6m xe hơi quay đầu...\n📞 Hotline: 0908123456",
      status: "success",
      fb_post_id: "192837465012_98234712",
      error_message: null,
      created_at: new Date(Date.now() - 3600000 * 2).toISOString()
    }
  ],
  settings: {
    gemini_api_key: process.env.GEMINI_API_KEY || "",
    gemini_model: "gemini-2.5-flash",
    post_delay_seconds: 15,
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    auto_check_live: true,
    custom_prompt_template: ""
  }
};

function readDb() {
  try {
    if (!fs.existsSync(DB_FILE)) {
      fs.writeFileSync(DB_FILE, JSON.stringify(defaultData, null, 2), 'utf-8');
      return defaultData;
    }
    const raw = fs.readFileSync(DB_FILE, 'utf-8');
    const parsed = JSON.parse(raw);
    return {
      listings: parsed.listings || [],
      accounts: parsed.accounts || [],
      groups: parsed.groups || [],
      logs: parsed.logs || [],
      settings: { ...defaultData.settings, ...(parsed.settings || {}) }
    };
  } catch (err) {
    console.error("Error reading db:", err);
    return defaultData;
  }
}

function writeDb(data) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
    return true;
  } catch (err) {
    console.error("Error writing db:", err);
    return false;
  }
}

export const db = {
  // Listings
  getListings: () => readDb().listings,
  getListing: (id) => readDb().listings.find(item => item.id === Number(id)),
  createListing: (data) => {
    const store = readDb();
    const newId = store.listings.length ? Math.max(...store.listings.map(l => l.id)) + 1 : 1;
    const newListing = {
      id: newId,
      title: data.title || "Chưa có tiêu đề",
      address: data.address || "",
      price: parseFloat(data.price) || 0,
      area: parseFloat(data.area) || 0,
      bedrooms: parseInt(data.bedrooms) || 0,
      bathrooms: parseInt(data.bathrooms) || 0,
      direction: data.direction || "",
      legal: data.legal || "",
      interior: data.interior || "",
      contact_name: data.contact_name || "",
      contact_phone: data.contact_phone || "",
      images: data.images || "",
      description: data.description || "",
      status: data.status || "available",
      created_at: new Date().toISOString()
    };
    store.listings.unshift(newListing);
    writeDb(store);
    return newListing;
  },
  updateListing: (id, data) => {
    const store = readDb();
    const index = store.listings.findIndex(l => l.id === Number(id));
    if (index === -1) return null;
    store.listings[index] = {
      ...store.listings[index],
      ...data,
      price: data.price !== undefined ? parseFloat(data.price) : store.listings[index].price,
      area: data.area !== undefined ? parseFloat(data.area) : store.listings[index].area
    };
    writeDb(store);
    return store.listings[index];
  },
  deleteListing: (id) => {
    const store = readDb();
    store.listings = store.listings.filter(l => l.id !== Number(id));
    writeDb(store);
    return true;
  },

  // Accounts
  getAccounts: () => readDb().accounts,
  getAccount: (id) => readDb().accounts.find(a => a.id === Number(id)),
  createAccount: (data) => {
    const store = readDb();
    const newId = store.accounts.length ? Math.max(...store.accounts.map(a => a.id)) + 1 : 1;
    const newAccount = {
      id: newId,
      uid: data.uid || `UID_${Date.now()}`,
      name: data.name || `Tài khoản #${newId}`,
      cookie: data.cookie || "",
      access_token: data.access_token || "",
      user_agent: data.user_agent || store.settings.user_agent,
      proxy: data.proxy || "",
      status: "active",
      live_status: data.cookie || data.access_token ? "live" : "unknown",
      groups_count: 0,
      last_check: new Date().toISOString(),
      created_at: new Date().toISOString()
    };
    store.accounts.unshift(newAccount);
    writeDb(store);
    return newAccount;
  },
  updateAccount: (id, data) => {
    const store = readDb();
    const idx = store.accounts.findIndex(a => a.id === Number(id));
    if (idx === -1) return null;
    store.accounts[idx] = { ...store.accounts[idx], ...data };
    writeDb(store);
    return store.accounts[idx];
  },
  deleteAccount: (id) => {
    const store = readDb();
    store.accounts = store.accounts.filter(a => a.id !== Number(id));
    store.groups = store.groups.filter(g => g.account_id !== Number(id));
    writeDb(store);
    return true;
  },

  // Groups
  getAllGroups: () => readDb().groups,
  getGroups: (accountId) => {
    const groups = readDb().groups;
    if (accountId && accountId !== 'all') {
      return groups.filter(g => g.account_id === Number(accountId));
    }
    return groups;
  },
  getGroup: (id) => readDb().groups.find(g => g.id === Number(id)),
  createGroup: (data) => {
    const store = readDb();
    const newId = store.groups.length ? Math.max(...store.groups.map(g => g.id)) + 1 : 1;
    const newGroup = {
      id: newId,
      account_id: Number(data.account_id),
      group_id: data.group_id,
      name: data.name,
      privacy: data.privacy || "PUBLIC",
      member_count: parseInt(data.member_count) || 0,
      post_permission: data.post_permission || "auto_approve",
      joined: true,
      created_at: new Date().toISOString()
    };
    store.groups.unshift(newGroup);
    // update account groups_count
    const acc = store.accounts.find(a => a.id === Number(data.account_id));
    if (acc) {
      acc.groups_count = store.groups.filter(g => g.account_id === acc.id).length;
    }
    writeDb(store);
    return newGroup;
  },
  updateGroup: (id, data) => {
    const store = readDb();
    const idx = store.groups.findIndex(g => g.id === Number(id));
    if (idx === -1) return null;
    store.groups[idx] = { ...store.groups[idx], ...data };
    writeDb(store);
    return store.groups[idx];
  },
  deleteGroup: (id) => {
    const store = readDb();
    const grp = store.groups.find(g => g.id === Number(id));
    store.groups = store.groups.filter(g => g.id !== Number(id));
    if (grp) {
      const acc = store.accounts.find(a => a.id === grp.account_id);
      if (acc) {
        acc.groups_count = store.groups.filter(g => g.account_id === acc.id).length;
      }
    }
    writeDb(store);
    return true;
  },
  syncAccountGroups: (accountId, groupsList) => {
    const store = readDb();
    const accId = Number(accountId);
    // remove old
    store.groups = store.groups.filter(g => g.account_id !== accId);
    let startId = store.groups.length ? Math.max(...store.groups.map(g => g.id)) + 1 : 1;
    for (const g of groupsList) {
      store.groups.push({
        id: startId++,
        account_id: accId,
        group_id: g.group_id,
        name: g.name,
        privacy: g.privacy || "PUBLIC",
        member_count: g.member_count || 10000,
        post_permission: g.post_permission || "auto_approve",
        joined: true,
        created_at: new Date().toISOString()
      });
    }
    const acc = store.accounts.find(a => a.id === accId);
    if (acc) {
      acc.groups_count = groupsList.length;
    }
    writeDb(store);
    return store.groups.filter(g => g.account_id === accId);
  },

  // Logs
  getLogs: (limit = 50) => {
    const logs = readDb().logs;
    return logs.slice(0, limit);
  },
  createLog: (data) => {
    const store = readDb();
    const newId = store.logs.length ? Math.max(...store.logs.map(l => l.id)) + 1 : 1;
    const newLog = {
      id: newId,
      account_id: data.account_id,
      account_name: data.account_name || "",
      group_id: data.group_id,
      group_name: data.group_name || "",
      listing_id: data.listing_id,
      listing_title: data.listing_title || "",
      post_type: data.post_type || "text",
      content: data.content,
      status: data.status,
      fb_post_id: data.fb_post_id || null,
      error_message: data.error_message || null,
      created_at: new Date().toISOString()
    };
    store.logs.unshift(newLog);
    writeDb(store);
    return newLog;
  },
  clearLogs: () => {
    const store = readDb();
    store.logs = [];
    writeDb(store);
    return true;
  },

  // Settings
  getSettings: () => readDb().settings,
  updateSettings: (newSettings) => {
    const store = readDb();
    store.settings = { ...store.settings, ...newSettings };
    writeDb(store);
    return store.settings;
  }
};
