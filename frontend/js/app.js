// ================================================================
//  Pain Miner — Frontend Application (v2 — Türkçe)
// ================================================================

const API = window.location.hostname === 'localhost'
    ? ''
    : 'https://pain-miner-api.fly.dev';

// ── State ──────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let scrapePolling = null;
let userActions = [];
let allTags = [];
let compareList = [];

// ── Router ─────────────────────────────────────────────────────────
function initRouter() {
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
}

function handleRoute() {
    const hash = window.location.hash.slice(1) || 'dashboard';
    navigateTo(hash);
}

function navigateTo(page) {
    currentPage = page;
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    const titles = {
        dashboard: 'Gösterge Paneli',
        problems: 'Problemler',
        ideas: 'Uygulama Fikirleri',
        compare: 'Karşılaştır',
        scrape: 'Tarama',
        runs: 'Geçmiş',
    };
    document.getElementById('pageTitle').textContent = titles[page] || 'Gösterge Paneli';
    renderPage(page);
}

// ── API Helpers ────────────────────────────────────────────────────
async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error(`API Hatası: ${endpoint}`, err);
        return null;
    }
}

async function apiPost(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`, { method: 'POST' });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (err) {
        console.error(`API Hatası: ${endpoint}`, err);
        throw err;
    }
}

async function apiDelete(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`, { method: 'DELETE' });
        return await res.json();
    } catch (err) {
        console.error(`API Hatası: ${endpoint}`, err);
    }
}

async function loadUserActions() {
    userActions = (await apiGet('/api/actions')) || [];
}

function hasAction(itemId, itemType, action) {
    return userActions.some(a => a.item_id === String(itemId) && a.item_type === itemType && a.action === action);
}

function getNote(itemId, itemType) {
    const a = userActions.find(ua => ua.item_id === String(itemId) && ua.item_type === itemType && ua.action === 'note');
    return a ? a.note : '';
}

async function toggleAction(itemId, itemType, action, note) {
    const has = hasAction(itemId, itemType, action);
    if (has) {
        await apiDelete(`/api/actions?item_id=${itemId}&item_type=${itemType}&action=${action}`);
    } else {
        await apiPost(`/api/actions?item_id=${itemId}&item_type=${itemType}&action=${action}${note ? '&note=' + encodeURIComponent(note) : ''}`);
    }
    await loadUserActions();
}

async function saveNote(itemId, itemType, note) {
    await apiPost(`/api/actions?item_id=${itemId}&item_type=${itemType}&action=note&note=${encodeURIComponent(note)}`);
    await loadUserActions();
}

// ── Renderers ──────────────────────────────────────────────────────
function renderPage(page) {
    const container = document.getElementById('pageContent');
    container.innerHTML = '<div class="loading-container"><div class="spinner"></div></div>';
    switch (page) {
        case 'dashboard': renderDashboard(container); break;
        case 'problems': renderProblems(container); break;
        case 'ideas': renderIdeas(container); break;
        case 'compare': renderCompare(container); break;
        case 'scrape': renderScrape(container); break;
        case 'runs': renderRuns(container); break;
        default: renderDashboard(container);
    }
}

// ── Dashboard ──────────────────────────────────────────────────────
async function renderDashboard(container) {
    const [stats, problems, ideas] = await Promise.all([
        apiGet('/api/stats'),
        apiGet('/api/problems?limit=5'),
        apiGet('/api/ideas?limit=4'),
    ]);
    await loadUserActions();

    const s = stats || { total_posts: 0, analyzed_posts: 0, app_ideas: 0, total_runs: 0, by_platform: {} };
    const approvedCount = userActions.filter(a => a.action === 'approve').length;
    const favCount = userActions.filter(a => a.action === 'favorite').length;

    container.innerHTML = `
        <div class="fade-in">
            <div class="stats-grid">
                <div class="stat-card purple">
                    <div class="stat-icon">📊</div>
                    <div class="stat-label">TOPLAM GÖNDERİ</div>
                    <div class="stat-value">${formatNumber(s.total_posts)}</div>
                </div>
                <div class="stat-card cyan">
                    <div class="stat-icon">🔍</div>
                    <div class="stat-label">ANALİZ EDİLEN</div>
                    <div class="stat-value">${formatNumber(s.analyzed_posts)}</div>
                </div>
                <div class="stat-card emerald">
                    <div class="stat-icon">✅</div>
                    <div class="stat-label">ONAYLANAN</div>
                    <div class="stat-value">${formatNumber(approvedCount)}</div>
                </div>
                <div class="stat-card amber">
                    <div class="stat-icon">⭐</div>
                    <div class="stat-label">FAVORİLER</div>
                    <div class="stat-value">${formatNumber(favCount)}</div>
                </div>
            </div>

            <div class="glass-card" style="margin-bottom: 24px;">
                <div class="card-header">
                    <div>
                        <div class="section-title">🔥 En İyi Problemler</div>
                        <div class="section-subtitle">ROI potansiyeli en yüksek sorunlar</div>
                    </div>
                    <a href="#problems" class="btn btn-secondary btn-sm">Tümünü Gör →</a>
                </div>
                <div class="card-body">
                    ${renderProblemsPreview(problems || [])}
                </div>
            </div>

            <div class="section-header">
                <div>
                    <div class="section-title">💡 Son Uygulama Fikirleri</div>
                    <div class="section-subtitle">Gerçek kullanıcı sorunlarından üretilen konseptler</div>
                </div>
                <a href="#ideas" class="btn btn-secondary btn-sm">Tümünü Gör →</a>
            </div>
            <div class="ideas-grid-v2">
                ${(ideas || []).length > 0
                    ? (ideas || []).map(idea => renderIdeaCard(idea)).join('')
                    : emptyState('💡', 'Henüz fikir yok', 'Sorun keşfetmek ve fikir üretmek için tarama başlatın.', '#scrape', 'Taramayı Başlat →')
                }
            </div>
        </div>
    `;
}

// ── Problems Page ──────────────────────────────────────────────────
async function renderProblems(container) {
    const [problems, tags] = await Promise.all([
        apiGet('/api/problems?limit=100'),
        apiGet('/api/tags'),
    ]);
    await loadUserActions();
    allTags = tags || [];

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 16px;">
                <div>
                    <div class="section-title">Keşfedilen Problemler</div>
                    <div class="section-subtitle">${(problems || []).length} problem bulundu, ROI ağırlığına göre sıralı</div>
                </div>
            </div>
            <div class="filter-bar" id="problemFilters">
                <div class="filter-label">🏷️ Etiket Filtresi:</div>
                <div class="filter-tags" id="filterTags">
                    <span class="filter-tag active" data-tag="">Tümü</span>
                    ${allTags.slice(0, 15).map(t => `<span class="filter-tag" data-tag="${escapeHtml(t.tag)}">${escapeHtml(t.tag)} <small>(${t.count})</small></span>`).join('')}
                </div>
            </div>
            <div class="problems-list" id="problemsList">
                ${renderProblemCards(problems || [])}
            </div>
        </div>
    `;

    // Tag filter click
    document.querySelectorAll('.filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            document.querySelectorAll('.filter-tag').forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            const selectedTag = tag.dataset.tag;
            const cards = document.querySelectorAll('.problem-card');
            cards.forEach(card => {
                if (!selectedTag || card.dataset.tags.includes(selectedTag)) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

function renderProblemCards(problems) {
    if (problems.length === 0) return emptyState('🔍', 'Henüz problem keşfedilmedi', 'Platformlardan sorun keşfetmek için taramayı başlatın.', '#scrape', 'Taramayı Başlat →');
    return problems.map((p, i) => renderProblemCard(p, i)).join('');
}

function renderProblemCard(p, index) {
    const painLevel = p.pain_score >= 7 ? 'critical' : p.pain_score >= 5 ? 'moderate' : 'low';
    const painLabel = painLevel === 'critical' ? '🔴 Kritik' : painLevel === 'moderate' ? '🟡 Orta' : '🟢 Düşük';
    const roiPercent = Math.min((p.roi_weight || 0) / 10 * 100, 100);
    const tags = (p.tags || '').split(',').filter(t => t.trim());
    const isFav = hasAction(p.id, 'problem', 'favorite');
    const note = getNote(p.id, 'problem');

    return `
        <div class="problem-card glass-card" data-tags="${escapeHtml(p.tags || '')}" onclick="this.classList.toggle('expanded')">
            <div class="problem-card-main">
                <div class="problem-rank">${index + 1}</div>
                <div class="problem-content">
                    <div class="problem-title-row">
                        <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="problem-title" onclick="event.stopPropagation()">
                            ${escapeHtml(p.title || 'Başlıksız')}
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:0.4; margin-left: 4px; flex-shrink:0;"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                        </a>
                        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                            <button class="icon-btn ${isFav ? 'active' : ''}" onclick="event.stopPropagation(); toggleFav('${p.id}','problem',this)" title="Favorilere ekle">⭐</button>
                            <span class="platform-badge ${p.platform}">${platformIcon(p.platform)} ${p.platform}</span>
                        </div>
                    </div>
                    <div class="problem-scores">
                        <div class="score-pill"><span class="score-label">ROI</span><div class="score-bar-track"><div class="score-bar-fill purple" style="width:${roiPercent}%"></div></div><span class="score-value">${p.roi_weight || 0}</span></div>
                        <div class="score-pill"><span class="score-label">Acı</span><span class="score-badge ${scoreClass(p.pain_score, 7, 5)}">${p.pain_score ? p.pain_score.toFixed(1) : '—'}</span></div>
                        <div class="score-pill"><span class="score-label">İlgi</span><span class="score-badge ${scoreClass(p.relevance_score, 7, 5)}">${p.relevance_score ? p.relevance_score.toFixed(1) : '—'}</span></div>
                        <div class="score-pill"><span class="score-label">Duygu</span><span class="score-badge ${scoreClass(p.emotion_score, 7, 5)}">${p.emotion_score ? p.emotion_score.toFixed(1) : '—'}</span></div>
                        <span class="pain-level ${painLevel}">${painLabel}</span>
                    </div>
                    ${tags.length > 0 ? `<div class="tags-container">${tags.map(t => `<span class="tag">${escapeHtml(t.trim())}</span>`).join('')}</div>` : ''}
                </div>
                <div class="expand-icon">▾</div>
            </div>
            <div class="problem-details">
                ${p.pain_point ? `<div class="detail-section"><div class="detail-label">🎯 Acı Noktası</div><div class="detail-text">${escapeHtml(p.pain_point)}</div></div>` : ''}
                ${p.product_opportunity ? `<div class="detail-section"><div class="detail-label">💡 Ürün Fırsatı</div><div class="detail-text">${escapeHtml(p.product_opportunity)}</div></div>` : ''}
                <div class="note-section">
                    <div class="detail-label">📝 Not</div>
                    <textarea class="note-input" placeholder="Bu problem hakkında notunuz..." onclick="event.stopPropagation()" onblur="saveNoteFromInput('${p.id}','problem',this)">${escapeHtml(note)}</textarea>
                </div>
                <div class="detail-footer">
                    <span class="detail-date">📅 ${p.processed_at || '—'}</span>
                    <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">Kaynağı Görüntüle →</a>
                </div>
            </div>
        </div>
    `;
}

function renderProblemsPreview(problems) {
    if (problems.length === 0) return emptyState('🔍', 'Henüz problem keşfedilmedi', 'Taramayı başlatın.', '#scrape', 'Taramayı Başlat →');
    return `<div class="problems-preview-list">${problems.slice(0, 5).map((p, i) => `
        <div class="problem-preview-item">
            <div class="problem-preview-rank">${i + 1}</div>
            <div class="problem-preview-content">
                <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="problem-preview-title">${escapeHtml(p.title || 'Başlıksız')}</a>
                ${p.pain_point ? `<div class="problem-preview-pain">${escapeHtml(truncate(p.pain_point, 120))}</div>` : ''}
            </div>
            <div class="problem-preview-meta">
                <span class="platform-badge ${p.platform}" style="font-size:0.65rem;padding:2px 8px;">${platformIcon(p.platform)} ${p.platform}</span>
                <span class="score-badge ${scoreClass(p.roi_weight, 8, 4)}">ROI ${p.roi_weight || 0}</span>
            </div>
        </div>
    `).join('')}</div>`;
}

// ── Ideas Page ─────────────────────────────────────────────────────
async function renderIdeas(container) {
    const [ideas, tags] = await Promise.all([
        apiGet('/api/ideas?limit=100'),
        apiGet('/api/tags'),
    ]);
    await loadUserActions();
    allTags = tags || [];

    const approvedCount = userActions.filter(a => a.item_type === 'idea' && a.action === 'approve').length;
    const rejectedCount = userActions.filter(a => a.item_type === 'idea' && a.action === 'reject').length;

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 16px;">
                <div>
                    <div class="section-title">Tüm Uygulama Fikirleri</div>
                    <div class="section-subtitle">${(ideas || []).length} AI üretimi konsept — ✅ ${approvedCount} onaylı · ❌ ${rejectedCount} reddedildi</div>
                </div>
                <div class="section-actions">
                    <button class="btn btn-secondary btn-sm" onclick="exportIdeas('json')">📤 JSON Dışa Aktar</button>
                    <button class="btn btn-secondary btn-sm" onclick="exportIdeas('csv')">📤 CSV Dışa Aktar</button>
                </div>
            </div>
            <div class="filter-bar" id="ideaFilters">
                <div class="filter-label">📋 Durum:</div>
                <div class="filter-tags" id="ideaStatusFilter">
                    <span class="filter-tag active" data-status="">Tümü</span>
                    <span class="filter-tag" data-status="approved">✅ Onaylı</span>
                    <span class="filter-tag" data-status="rejected">❌ Reddedildi</span>
                    <span class="filter-tag" data-status="favorite">⭐ Favoriler</span>
                    <span class="filter-tag" data-status="pending">⏳ Bekleyen</span>
                </div>
            </div>
            <div class="ideas-grid-v2" id="ideasGrid">
                ${(ideas || []).length > 0
                    ? ideas.map(idea => renderIdeaCard(idea)).join('')
                    : emptyState('💡', 'Henüz fikir üretilmedi', 'Taramayı başlatıp fikir üretmek için çalıştırın.', '#scrape', 'Taramayı Başlat →')
                }
            </div>
        </div>
    `;

    // Status filter
    document.querySelectorAll('#ideaStatusFilter .filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            document.querySelectorAll('#ideaStatusFilter .filter-tag').forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            const status = tag.dataset.status;
            const cards = document.querySelectorAll('.idea-card-v2');
            cards.forEach(card => {
                const id = card.dataset.id;
                const isApproved = hasAction(id, 'idea', 'approve');
                const isRejected = hasAction(id, 'idea', 'reject');
                const isFav = hasAction(id, 'idea', 'favorite');
                let show = true;
                if (status === 'approved') show = isApproved;
                else if (status === 'rejected') show = isRejected;
                else if (status === 'favorite') show = isFav;
                else if (status === 'pending') show = !isApproved && !isRejected;
                card.style.display = show ? '' : 'none';
            });
        });
    });
}

function renderIdeaCard(idea) {
    const typeIcon = { webapp: '🌐', mobile: '📱', saas: '☁️', extension: '🔌', desktop: '🖥️' };
    const icon = typeIcon[(idea.app_type || '').toLowerCase()] || '💡';
    const typeClass = getIdeaTypeClass(idea.app_type);
    const techPills = (idea.tech_stack || '').split(',').filter(t => t.trim()).map(t => `<span class="tech-pill">${escapeHtml(t.trim())}</span>`).join('');
    const mvpHtml = (idea.mvp_features || []).map(f => `<li>${escapeHtml(f)}</li>`).join('');
    const trafficLevel = potentialClass(idea.traffic_potential);
    const revenueLevel = potentialClass(idea.revenue_potential);
    const trafficPercent = trafficLevel === 'high' ? 90 : trafficLevel === 'medium' ? 55 : 25;
    const revenuePercent = revenueLevel === 'high' ? 90 : revenueLevel === 'medium' ? 55 : 25;
    const isFav = hasAction(idea.id, 'idea', 'favorite');
    const isApproved = hasAction(idea.id, 'idea', 'approve');
    const isRejected = hasAction(idea.id, 'idea', 'reject');
    const note = getNote(idea.id, 'idea');
    const inCompare = compareList.includes(String(idea.id));
    const statusClass = isApproved ? 'card-approved' : isRejected ? 'card-rejected' : '';

    return `
        <div class="idea-card-v2 ${statusClass}" data-id="${idea.id}" onclick="this.classList.toggle('expanded')">
            <div class="idea-card-top">
                <div class="idea-card-icon ${typeClass}">${icon}</div>
                <div class="idea-card-title-area">
                    <div class="idea-name-v2">${escapeHtml(idea.app_name || 'İsimsiz')}</div>
                    <div class="idea-type-row">
                        <span class="idea-type-badge ${typeClass}">${escapeHtml(idea.app_type || 'Uygulama')}</span>
                        <span class="idea-complexity ${(idea.complexity || '').toLowerCase()}">${escapeHtml(idea.complexity || '?')}</span>
                    </div>
                </div>
                <div class="idea-action-btns" onclick="event.stopPropagation()">
                    <button class="icon-btn ${isFav ? 'active' : ''}" onclick="toggleFav('${idea.id}','idea',this)" title="Favorilere ekle">⭐</button>
                    <button class="icon-btn approve-btn ${isApproved ? 'active' : ''}" onclick="toggleApproval('${idea.id}','approve',this)" title="Onayla">✅</button>
                    <button class="icon-btn reject-btn ${isRejected ? 'active' : ''}" onclick="toggleApproval('${idea.id}','reject',this)" title="Reddet">❌</button>
                    <button class="icon-btn compare-btn ${inCompare ? 'active' : ''}" onclick="toggleCompare('${idea.id}',this)" title="Karşılaştır">⚖️</button>
                </div>
            </div>

            <div class="idea-description-v2">${escapeHtml(idea.description || '')}</div>

            <div class="idea-info-grid">
                <div class="idea-info-item"><span class="idea-info-label">🎯 Hedef Kitle</span><span class="idea-info-value">${escapeHtml(idea.target_audience || '—')}</span></div>
                <div class="idea-info-item"><span class="idea-info-label">💰 Gelir Modeli</span><span class="idea-info-value">${escapeHtml(idea.monetization || '—')}</span></div>
            </div>

            <div class="idea-potential-row">
                <div class="potential-gauge"><span class="potential-label">📈 Trafik</span><div class="potential-bar-track"><div class="potential-bar-fill ${trafficLevel}" style="width:${trafficPercent}%"></div></div><span class="potential-value ${trafficLevel}">${idea.traffic_potential || '—'}</span></div>
                <div class="potential-gauge"><span class="potential-label">💵 Gelir</span><div class="potential-bar-track"><div class="potential-bar-fill ${revenueLevel}" style="width:${revenuePercent}%"></div></div><span class="potential-value ${revenueLevel}">${idea.revenue_potential || '—'}</span></div>
            </div>

            <div class="idea-expandable">
                ${techPills ? `<div class="idea-section"><div class="idea-section-label">⚙️ Teknoloji Yığını</div><div class="tech-pills-container">${techPills}</div></div>` : ''}
                ${mvpHtml ? `<div class="idea-section"><div class="idea-section-label">🚀 MVP Özellikleri</div><ul class="idea-mvp-list-v2">${mvpHtml}</ul></div>` : ''}
                <div class="note-section" onclick="event.stopPropagation()">
                    <div class="idea-section-label">📝 Notlarınız</div>
                    <textarea class="note-input" placeholder="Bu fikir hakkında notunuz..." onblur="saveNoteFromInput('${idea.id}','idea',this)">${escapeHtml(note)}</textarea>
                </div>
            </div>

            <div class="idea-footer-v2">
                <span class="idea-source-v2">
                    <span class="platform-badge ${idea.platform}" style="font-size:0.65rem;padding:2px 8px;">${idea.platform}</span>
                    <a href="${escapeHtml(idea.post_url || '#')}" target="_blank" rel="noopener" class="idea-source-link" onclick="event.stopPropagation()">${escapeHtml(truncate(idea.post_title, 50))}</a>
                </span>
                <span class="expand-hint">Detaylar için tıkla</span>
            </div>
        </div>
    `;
}

// ── Compare Page ───────────────────────────────────────────────────
async function renderCompare(container) {
    if (compareList.length === 0) {
        container.innerHTML = `<div class="fade-in">${emptyState('⚖️', 'Karşılaştırma listesi boş', 'Uygulama fikirleri sayfasından ⚖️ butonuna tıklayarak fikirleri karşılaştırma listesine ekleyin.', '#ideas', 'Fikirleri Gör →')}</div>`;
        return;
    }

    const ideas = await apiGet('/api/ideas?limit=200');
    const selected = (ideas || []).filter(i => compareList.includes(String(i.id)));

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 20px;">
                <div>
                    <div class="section-title">⚖️ Fikir Karşılaştırması</div>
                    <div class="section-subtitle">${selected.length} fikir seçildi</div>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="compareList=[];navigateTo('compare')">🗑️ Listeyi Temizle</button>
            </div>
            <div class="compare-grid" style="display:grid;grid-template-columns:repeat(${Math.min(selected.length, 3)}, 1fr);gap:16px;">
                ${selected.map(idea => {
                    const typeIcon = { webapp: '🌐', mobile: '📱', saas: '☁️', extension: '🔌' };
                    const icon = typeIcon[(idea.app_type || '').toLowerCase()] || '💡';
                    const trafficLevel = potentialClass(idea.traffic_potential);
                    const revenueLevel = potentialClass(idea.revenue_potential);
                    return `
                        <div class="glass-card" style="padding:24px;display:flex;flex-direction:column;gap:14px;">
                            <div style="display:flex;align-items:center;gap:10px;">
                                <span style="font-size:1.5rem;">${icon}</span>
                                <div>
                                    <div style="font-weight:700;font-size:1rem;">${escapeHtml(idea.app_name)}</div>
                                    <div style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;">${escapeHtml(idea.app_type)} · ${escapeHtml(idea.complexity)}</div>
                                </div>
                            </div>
                            <div style="font-size:0.85rem;color:var(--text-secondary);line-height:1.55;">${escapeHtml(idea.description)}</div>
                            <div class="compare-row"><span class="compare-label">🎯 Hedef Kitle</span><span class="compare-val">${escapeHtml(idea.target_audience || '—')}</span></div>
                            <div class="compare-row"><span class="compare-label">💰 Gelir</span><span class="compare-val">${escapeHtml(idea.monetization || '—')}</span></div>
                            <div class="compare-row"><span class="compare-label">📈 Trafik</span><span class="potential-value ${trafficLevel}">${idea.traffic_potential || '—'}</span></div>
                            <div class="compare-row"><span class="compare-label">💵 Gelir</span><span class="potential-value ${revenueLevel}">${idea.revenue_potential || '—'}</span></div>
                            <div style="font-size:0.78rem;color:var(--text-muted);"><b>Teknoloji:</b> ${escapeHtml(idea.tech_stack || '—')}</div>
                            ${(idea.mvp_features || []).length > 0 ? `<div><div style="font-size:0.72rem;color:var(--text-muted);font-weight:700;margin-bottom:4px;">MVP ÖZELLİKLERİ</div><ul class="idea-mvp-list-v2">${idea.mvp_features.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul></div>` : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

// ── Scrape Page ────────────────────────────────────────────────────
async function renderScrape(container) {
    const status = await apiGet('/api/scrape/status');
    const isRunning = status && status.running;

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 24px;">
                <div>
                    <div class="section-title">Tarama Hattı</div>
                    <div class="section-subtitle">Platformlardan veri çek, sorunları analiz et ve uygulama fikirleri üret</div>
                </div>
            </div>

            <div class="glass-card" style="padding: 28px; margin-bottom: 24px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                    <span style="font-size: 1.5rem;">⚡</span>
                    <div>
                        <div style="font-weight: 700; font-size: 1rem;">Taramayı Çalıştır</div>
                        <div style="font-size: 0.82rem; color: var(--text-tertiary);">Bir platform seçin veya tüm platformları tarayın</div>
                    </div>
                </div>

                <div class="scrape-controls">
                    <div class="form-group">
                        <label class="form-label">Platform</label>
                        <select class="form-select" id="scrapePlatform">
                            <option value="">Tüm Platformlar</option>
                            <option value="reddit">Reddit</option>
                            <option value="hackernews">Hacker News</option>
                            <option value="producthunt">Product Hunt</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Limit</label>
                        <input type="number" class="form-input" id="scrapeLimit" placeholder="Varsayılan" min="1" max="200" style="width: 120px;">
                    </div>
                    <button class="btn btn-primary" id="scrapeBtn" ${isRunning ? 'disabled' : ''}>
                        ${isRunning ? '⏳ Çalışıyor...' : '🚀 Taramayı Başlat'}
                    </button>
                </div>
            </div>

            <div id="scrapeStatus">
                ${isRunning ? renderScrapeRunning() : ''}
                ${status && status.result ? renderScrapeResult(status.result) : ''}
                ${status && status.error ? renderScrapeError(status.error) : ''}
            </div>

            <div class="glass-card">
                <div class="card-header"><div class="section-title">Tarama Akışı</div></div>
                <div class="card-body" style="padding: 24px;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                        ${renderPipelineStep('1', 'Tarama', 'Reddit, HN, PH\'den gönderileri çek', '🌐')}
                        ${renderPipelineStep('2', 'Filtreleme', 'Her gönderiyi AI ile puanla', '🔍')}
                        ${renderPipelineStep('3', 'Analiz', 'Yüksek potansiyelli sorunları derinlemesine analiz et', '🧠')}
                        ${renderPipelineStep('4', 'Üretim', 'Doğrulanmış sorunlardan fikir üret', '💡')}
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('scrapeBtn').addEventListener('click', startScrape);
    if (isRunning) startScrapePolling();
}

function renderPipelineStep(num, title, desc, icon) {
    return `<div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-primary); border-radius: var(--radius-sm); padding: 18px; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 10px;">${icon}</div>
        <div style="font-size: 0.7rem; color: var(--purple); font-weight: 700; letter-spacing: 0.1em; margin-bottom: 4px;">ADIM ${num}</div>
        <div style="font-weight: 700; margin-bottom: 4px;">${title}</div>
        <div style="font-size: 0.8rem; color: var(--text-tertiary); line-height: 1.4;">${desc}</div>
    </div>`;
}

function renderScrapeRunning() {
    return `<div class="scrape-progress"><div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;"><div class="spinner" style="width: 20px; height: 20px; border-width: 2px;"></div><span style="font-weight: 600;">Tarama devam ediyor...</span></div><div class="progress-bar-container"><div class="progress-bar" style="width: 60%;"></div></div><div class="progress-text">Platformlardan veri çekiliyor ve gönderiler analiz ediliyor. Bu birkaç dakika sürebilir.</div></div>`;
}

function renderScrapeResult(result) {
    return `<div class="glass-card" style="margin-bottom: 24px; border-color: rgba(16, 185, 129, 0.3);"><div style="padding: 22px;"><div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;"><span style="font-size: 1.3rem;">✅</span><span style="font-weight: 700; color: var(--emerald);">Tarama Tamamlandı</span></div><div class="stats-grid" style="margin-bottom: 0;"><div style="text-align: center;"><div style="font-size: 1.5rem; font-weight: 800; color: var(--purple);">${result.scraped || 0}</div><div style="font-size: 0.78rem; color: var(--text-tertiary);">Çekilen Gönderi</div></div><div style="text-align: center;"><div style="font-size: 1.5rem; font-weight: 800; color: var(--cyan);">${result.high_potential || 0}</div><div style="font-size: 0.78rem; color: var(--text-tertiary);">Yüksek Potansiyel</div></div><div style="text-align: center;"><div style="font-size: 1.5rem; font-weight: 800; color: var(--emerald);">${result.insights || 0}</div><div style="font-size: 0.78rem; color: var(--text-tertiary);">İçgörü</div></div><div style="text-align: center;"><div style="font-size: 1.5rem; font-weight: 800; color: var(--amber);">${result.app_ideas || 0}</div><div style="font-size: 0.78rem; color: var(--text-tertiary);">Uygulama Fikri</div></div></div></div></div>`;
}

function renderScrapeError(error) {
    return `<div class="glass-card" style="margin-bottom: 24px; border-color: rgba(244, 63, 94, 0.3);"><div style="padding: 22px;"><div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;"><span style="font-size: 1.3rem;">❌</span><span style="font-weight: 700; color: var(--rose);">Tarama Hatası</span></div><div style="font-size: 0.85rem; color: var(--text-secondary); font-family: monospace; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px;">${escapeHtml(error)}</div></div></div>`;
}

async function startScrape() {
    const btn = document.getElementById('scrapeBtn');
    const platform = document.getElementById('scrapePlatform').value;
    const limit = document.getElementById('scrapeLimit').value;
    const statusDiv = document.getElementById('scrapeStatus');
    let endpoint = '/api/scrape?';
    if (platform) endpoint += `platform=${platform}&`;
    if (limit) endpoint += `limit=${limit}&`;
    btn.disabled = true;
    btn.innerHTML = '⏳ Başlatılıyor...';
    try {
        await apiPost(endpoint);
        statusDiv.innerHTML = renderScrapeRunning();
        btn.innerHTML = '⏳ Çalışıyor...';
        updateStatusIndicator(true);
        startScrapePolling();
    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = '🚀 Taramayı Başlat';
        statusDiv.innerHTML = renderScrapeError(err.message);
    }
}

function startScrapePolling() {
    if (scrapePolling) clearInterval(scrapePolling);
    scrapePolling = setInterval(async () => {
        const status = await apiGet('/api/scrape/status');
        if (!status) return;
        if (!status.running) {
            clearInterval(scrapePolling);
            scrapePolling = null;
            updateStatusIndicator(false);
            if (currentPage === 'scrape') renderScrape(document.getElementById('pageContent'));
        }
    }, 3000);
}

function updateStatusIndicator(scraping) {
    const dot = document.querySelector('.status-dot');
    const text = document.querySelector('.status-text');
    if (scraping) { dot.classList.add('scraping'); text.textContent = 'Taranıyor...'; }
    else { dot.classList.remove('scraping'); text.textContent = 'Hazır'; }
}

// ── Runs Page ──────────────────────────────────────────────────────
async function renderRuns(container) {
    const runs = await apiGet('/api/runs');
    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 20px;">
                <div>
                    <div class="section-title">Çalışma Geçmişi</div>
                    <div class="section-subtitle">Geçmiş tarama işlemleri</div>
                </div>
            </div>
            <div class="glass-card">
                <div class="card-body">
                    ${(runs || []).length > 0 ? `
                        <table class="data-table">
                            <thead><tr><th>#</th><th>Başlangıç</th><th>Platform</th><th>Gönderi</th><th>Problem</th><th>Süre</th><th>Durum</th></tr></thead>
                            <tbody>
                                ${(runs || []).map(run => `
                                    <tr>
                                        <td style="color: var(--text-muted);">${run.id}</td>
                                        <td>${formatDate(run.started_at)}</td>
                                        <td>${(run.platform || '').split(',').map(p => `<span class="platform-badge ${p.trim()}" style="font-size: 0.65rem; padding: 2px 7px;">${p.trim()}</span>`).join(' ')}</td>
                                        <td>${run.posts_scraped || 0}</td>
                                        <td>${run.problems_found || 0}</td>
                                        <td>${run.duration_seconds ? run.duration_seconds.toFixed(1) + 'sn' : '—'}</td>
                                        <td><span class="run-status ${run.status || ''}">${statusTR(run.status)}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    ` : emptyState('🕐', 'Henüz çalışma yok', 'İlk taramanızı başlatın.', '#scrape', 'Taramayı Başlat →')}
                </div>
            </div>
        </div>
    `;
}

// ── Action Handlers ────────────────────────────────────────────────
window.toggleFav = async function(itemId, itemType, btn) {
    await toggleAction(itemId, itemType, 'favorite');
    btn.classList.toggle('active');
}

window.toggleApproval = async function(ideaId, action, btn) {
    const opposite = action === 'approve' ? 'reject' : 'approve';
    if (hasAction(ideaId, 'idea', opposite)) {
        await apiDelete(`/api/actions?item_id=${ideaId}&item_type=idea&action=${opposite}`);
    }
    await toggleAction(ideaId, 'idea', action);
    if (currentPage === 'ideas') renderIdeas(document.getElementById('pageContent'));
}

window.toggleCompare = function(ideaId, btn) {
    const id = String(ideaId);
    const idx = compareList.indexOf(id);
    if (idx >= 0) { compareList.splice(idx, 1); btn.classList.remove('active'); }
    else if (compareList.length < 4) { compareList.push(id); btn.classList.add('active'); }
    else { alert('En fazla 4 fikir karşılaştırabilirsiniz.'); }
}

window.saveNoteFromInput = async function(itemId, itemType, textarea) {
    const text = textarea.value.trim();
    if (text) await saveNote(itemId, itemType, text);
}

window.exportIdeas = function(format) {
    window.open(`${API}/api/export?format=${format}`, '_blank');
}

// ── Utility Functions ──────────────────────────────────────────────
function escapeHtml(str) { if (!str) return ''; const div = document.createElement('div'); div.textContent = String(str); return div.innerHTML; }
function truncate(str, max) { if (!str) return ''; return str.length > max ? str.slice(0, max) + '…' : str; }
function formatNumber(num) { if (num == null) return '0'; return Number(num).toLocaleString('tr-TR'); }

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try { const d = new Date(dateStr); return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }); }
    catch { return dateStr; }
}

function platformIcon(platform) { return { reddit: '◉', hackernews: '▲', producthunt: '🚀' }[platform] || '●'; }
function scoreClass(val, h, m) { if (val == null) return 'low'; if (val >= h) return 'high'; if (val >= m) return 'medium'; return 'low'; }
function potentialClass(level) { if (!level) return 'low'; const l = level.toLowerCase(); if (l.includes('high') || l.includes('yüksek')) return 'high'; if (l.includes('medium') || l.includes('orta')) return 'medium'; return 'low'; }
function getIdeaTypeClass(type) { if (!type) return 'default'; const t = type.toLowerCase(); if (t.includes('web')) return 'web'; if (t.includes('mobile')) return 'mobile'; if (t.includes('saas')) return 'saas'; if (t.includes('extension') || t.includes('plugin')) return 'extension'; return 'default'; }
function statusTR(s) { return { completed: 'Tamamlandı', running: 'Çalışıyor', error: 'Hata', no_data: 'Veri Yok', no_valid_posts: 'Geçerli Gönderi Yok', no_high_potential: 'Potansiyel Yok', scrape_only: 'Sadece Tarama' }[s] || s || 'Bilinmiyor'; }

function emptyState(icon, title, text, href, btnText) {
    return `<div class="empty-state"><div class="empty-state-icon">${icon}</div><div class="empty-state-title">${title}</div><div class="empty-state-text">${text}</div><a href="${href}" class="btn btn-primary">${btnText}</a></div>`;
}

// ── Sidebar toggle (mobile) ───────────────────────────────────────
function initSidebar() {
    const toggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => { if (window.innerWidth <= 768) sidebar.classList.remove('open'); });
    });
}

// ── Init ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await loadUserActions();
    initSidebar();
    initRouter();
});
