// ================================================================
//  Pain Miner — Frontend Application
// ================================================================

const API = window.location.hostname === 'localhost'
    ? ''
    : 'https://pain-miner-api.fly.dev';

// ── State ──────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let scrapePolling = null;

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

    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Update title
    const titles = {
        dashboard: 'Dashboard',
        problems: 'Problems',
        ideas: 'App Ideas',
        scrape: 'Scrape Pipeline',
        runs: 'Run History',
    };
    document.getElementById('pageTitle').textContent = titles[page] || 'Dashboard';

    // Render page
    renderPage(page);
}

// ── API Helpers ────────────────────────────────────────────────────
async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error(`API Error: ${endpoint}`, err);
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
        console.error(`API Error: ${endpoint}`, err);
        throw err;
    }
}

// ── Renderers ──────────────────────────────────────────────────────
function renderPage(page) {
    const container = document.getElementById('pageContent');
    container.innerHTML = '<div class="loading-container"><div class="spinner"></div></div>';

    switch (page) {
        case 'dashboard': renderDashboard(container); break;
        case 'problems': renderProblems(container); break;
        case 'ideas': renderIdeas(container); break;
        case 'scrape': renderScrape(container); break;
        case 'runs': renderRuns(container); break;
        default: renderDashboard(container);
    }
}

// ── Dashboard ──────────────────────────────────────────────────────
async function renderDashboard(container) {
    const [stats, problems, ideas] = await Promise.all([
        apiGet('/api/stats'),
        apiGet('/api/problems?limit=8'),
        apiGet('/api/ideas?limit=6'),
    ]);

    const s = stats || { total_posts: 0, analyzed_posts: 0, app_ideas: 0, total_runs: 0, by_platform: {} };
    const platformCount = Object.keys(s.by_platform || {}).length;

    container.innerHTML = `
        <div class="fade-in">
            <!-- Stats -->
            <div class="stats-grid">
                <div class="stat-card purple">
                    <div class="stat-icon">📊</div>
                    <div class="stat-label">Total Posts</div>
                    <div class="stat-value">${formatNumber(s.total_posts)}</div>
                </div>
                <div class="stat-card cyan">
                    <div class="stat-icon">🔍</div>
                    <div class="stat-label">Analyzed</div>
                    <div class="stat-value">${formatNumber(s.analyzed_posts)}</div>
                </div>
                <div class="stat-card emerald">
                    <div class="stat-icon">💡</div>
                    <div class="stat-label">App Ideas</div>
                    <div class="stat-value">${formatNumber(s.app_ideas)}</div>
                </div>
                <div class="stat-card amber">
                    <div class="stat-icon">🚀</div>
                    <div class="stat-label">Pipeline Runs</div>
                    <div class="stat-value">${formatNumber(s.total_runs)}</div>
                </div>
            </div>

            ${platformCount > 0 ? `
            <div class="stats-grid" style="margin-bottom: 32px;">
                ${Object.entries(s.by_platform).map(([p, count]) => `
                    <div class="glass-card" style="padding: 16px 20px; display: flex; align-items: center; justify-content: space-between;">
                        <span class="platform-badge ${p}">${platformIcon(p)} ${p}</span>
                        <span style="font-size: 1.3rem; font-weight: 700; color: var(--text-primary);">${formatNumber(count)}</span>
                    </div>
                `).join('')}
            </div>
            ` : ''}

            <!-- Top Problems -->
            <div class="glass-card" style="margin-bottom: 24px;">
                <div class="card-header">
                    <div>
                        <div class="section-title">🔥 Top Problems</div>
                        <div class="section-subtitle">Highest ROI potential from scraped data</div>
                    </div>
                    <a href="#problems" class="btn btn-secondary btn-sm">View All →</a>
                </div>
                <div class="card-body">
                    ${renderProblemsTable(problems || [], true)}
                </div>
            </div>

            <!-- Latest Ideas -->
            <div class="section-header">
                <div>
                    <div class="section-title">💡 Latest App Ideas</div>
                    <div class="section-subtitle">AI-generated product concepts from real user pain points</div>
                </div>
                <a href="#ideas" class="btn btn-secondary btn-sm">View All →</a>
            </div>
            <div class="ideas-grid">
                ${(ideas || []).length > 0
                    ? (ideas || []).map(idea => renderIdeaCard(idea)).join('')
                    : `<div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="empty-state-icon">💡</div>
                        <div class="empty-state-title">No app ideas yet</div>
                        <div class="empty-state-text">Run the scrape pipeline to discover problems and generate app ideas.</div>
                        <a href="#scrape" class="btn btn-primary">Start Scraping →</a>
                       </div>`
                }
            </div>
        </div>
    `;
}

// ── Problems Page ──────────────────────────────────────────────────
async function renderProblems(container) {
    const problems = await apiGet('/api/problems?limit=100');

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 20px;">
                <div>
                    <div class="section-title">All Discovered Problems</div>
                    <div class="section-subtitle">${(problems || []).length} problems found, sorted by ROI weight</div>
                </div>
            </div>
            <div class="problems-list">
                ${(problems || []).length > 0
                    ? (problems || []).map((p, i) => renderProblemCard(p, i)).join('')
                    : `<div class="empty-state">
                        <div class="empty-state-icon">🔍</div>
                        <div class="empty-state-title">No problems discovered yet</div>
                        <div class="empty-state-text">Run the scrape pipeline to start discovering real user problems from Reddit, Hacker News, and Product Hunt.</div>
                        <a href="#scrape" class="btn btn-primary">Start Scraping →</a>
                       </div>`
                }
            </div>
        </div>
    `;
}

function renderProblemCard(p, index) {
    const painLevel = p.pain_score >= 7 ? 'critical' : p.pain_score >= 5 ? 'moderate' : 'low';
    const painLabel = painLevel === 'critical' ? '🔴 Critical' : painLevel === 'moderate' ? '🟡 Moderate' : '🟢 Low';
    const roiPercent = Math.min((p.roi_weight || 0) / 10 * 100, 100);
    const tags = (p.tags || '').split(',').filter(t => t.trim());

    return `
        <div class="problem-card glass-card" onclick="this.classList.toggle('expanded')">
            <div class="problem-card-main">
                <div class="problem-rank">${index + 1}</div>
                <div class="problem-content">
                    <div class="problem-title-row">
                        <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="problem-title" onclick="event.stopPropagation()">
                            ${escapeHtml(p.title || 'Untitled')}
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:0.4; margin-left: 4px; flex-shrink:0;"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                        </a>
                        <span class="platform-badge ${p.platform}">${platformIcon(p.platform)} ${p.platform}</span>
                    </div>
                    <div class="problem-scores">
                        <div class="score-pill">
                            <span class="score-label">ROI</span>
                            <div class="score-bar-track"><div class="score-bar-fill purple" style="width: ${roiPercent}%"></div></div>
                            <span class="score-value">${p.roi_weight || 0}</span>
                        </div>
                        <div class="score-pill">
                            <span class="score-label">Pain</span>
                            <span class="score-badge ${scoreClass(p.pain_score, 7, 5)}">${p.pain_score ? p.pain_score.toFixed(1) : '—'}</span>
                        </div>
                        <div class="score-pill">
                            <span class="score-label">Relevance</span>
                            <span class="score-badge ${scoreClass(p.relevance_score, 7, 5)}">${p.relevance_score ? p.relevance_score.toFixed(1) : '—'}</span>
                        </div>
                        <div class="score-pill">
                            <span class="score-label">Emotion</span>
                            <span class="score-badge ${scoreClass(p.emotion_score, 7, 5)}">${p.emotion_score ? p.emotion_score.toFixed(1) : '—'}</span>
                        </div>
                        <span class="pain-level ${painLevel}">${painLabel}</span>
                    </div>
                    ${tags.length > 0 ? `
                        <div class="tags-container">${tags.map(t => `<span class="tag">${escapeHtml(t.trim())}</span>`).join('')}</div>
                    ` : ''}
                </div>
                <div class="expand-icon">▾</div>
            </div>
            <div class="problem-details">
                ${p.pain_point ? `
                    <div class="detail-section">
                        <div class="detail-label">🎯 Pain Point</div>
                        <div class="detail-text">${escapeHtml(p.pain_point)}</div>
                    </div>
                ` : ''}
                ${p.product_opportunity ? `
                    <div class="detail-section">
                        <div class="detail-label">💡 Product Opportunity</div>
                        <div class="detail-text">${escapeHtml(p.product_opportunity)}</div>
                    </div>
                ` : ''}
                <div class="detail-footer">
                    <span class="detail-date">📅 ${p.processed_at || '—'}</span>
                    <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">View Source →</a>
                </div>
            </div>
        </div>
    `;
}

function renderProblemsTable(problems, compact) {
    if (problems.length === 0) {
        return `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <div class="empty-state-title">No problems discovered yet</div>
                <div class="empty-state-text">Run the scrape pipeline to start discovering real user problems from Reddit, Hacker News, and Product Hunt.</div>
                <a href="#scrape" class="btn btn-primary">Start Scraping →</a>
            </div>
        `;
    }

    return `
        <div class="problems-preview-list">
            ${problems.slice(0, compact ? 5 : problems.length).map((p, i) => `
                <div class="problem-preview-item">
                    <div class="problem-preview-rank">${i + 1}</div>
                    <div class="problem-preview-content">
                        <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener" class="problem-preview-title">${escapeHtml(p.title || 'Untitled')}</a>
                        ${p.pain_point ? `<div class="problem-preview-pain">${escapeHtml(truncate(p.pain_point, 120))}</div>` : ''}
                    </div>
                    <div class="problem-preview-meta">
                        <span class="platform-badge ${p.platform}" style="font-size: 0.65rem; padding: 2px 8px;">${platformIcon(p.platform)} ${p.platform}</span>
                        <span class="score-badge ${scoreClass(p.roi_weight, 8, 4)}">ROI ${p.roi_weight || 0}</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// ── Ideas Page ─────────────────────────────────────────────────────
async function renderIdeas(container) {
    const ideas = await apiGet('/api/ideas?limit=100');

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 20px;">
                <div>
                    <div class="section-title">All App Ideas</div>
                    <div class="section-subtitle">${(ideas || []).length} AI-generated product concepts</div>
                </div>
            </div>
            <div class="ideas-grid-v2">
                ${(ideas || []).length > 0
                    ? ideas.map(idea => renderIdeaCard(idea)).join('')
                    : `<div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="empty-state-icon">💡</div>
                        <div class="empty-state-title">No ideas generated yet</div>
                        <div class="empty-state-text">Run the full scrape pipeline (with AI analysis) to generate app ideas from discovered problems.</div>
                        <a href="#scrape" class="btn btn-primary">Start Scraping →</a>
                       </div>`
                }
            </div>
        </div>
    `;
}

function renderIdeaCard(idea) {
    const typeIcon = { webapp: '🌐', mobile: '📱', saas: '☁️', extension: '🔌', desktop: '🖥️' };
    const icon = typeIcon[(idea.app_type || '').toLowerCase()] || '💡';
    const typeClass = getIdeaTypeClass(idea.app_type);

    const techPills = (idea.tech_stack || '').split(',').filter(t => t.trim()).map(t =>
        `<span class="tech-pill">${escapeHtml(t.trim())}</span>`
    ).join('');

    const mvpHtml = (idea.mvp_features || []).map(f =>
        `<li>${escapeHtml(f)}</li>`
    ).join('');

    const trafficLevel = potentialClass(idea.traffic_potential);
    const revenueLevel = potentialClass(idea.revenue_potential);
    const trafficPercent = trafficLevel === 'high' ? 90 : trafficLevel === 'medium' ? 55 : 25;
    const revenuePercent = revenueLevel === 'high' ? 90 : revenueLevel === 'medium' ? 55 : 25;

    return `
        <div class="idea-card-v2" onclick="this.classList.toggle('expanded')">
            <div class="idea-card-top">
                <div class="idea-card-icon ${typeClass}">${icon}</div>
                <div class="idea-card-title-area">
                    <div class="idea-name-v2">${escapeHtml(idea.app_name || 'Untitled')}</div>
                    <div class="idea-type-row">
                        <span class="idea-type-badge ${typeClass}">${escapeHtml(idea.app_type || 'App')}</span>
                        <span class="idea-complexity ${(idea.complexity || '').toLowerCase()}">${escapeHtml(idea.complexity || '?')}</span>
                    </div>
                </div>
            </div>

            <div class="idea-description-v2">${escapeHtml(idea.description || '')}</div>

            <div class="idea-info-grid">
                <div class="idea-info-item">
                    <span class="idea-info-label">🎯 Audience</span>
                    <span class="idea-info-value">${escapeHtml(idea.target_audience || '—')}</span>
                </div>
                <div class="idea-info-item">
                    <span class="idea-info-label">💰 Monetization</span>
                    <span class="idea-info-value">${escapeHtml(idea.monetization || '—')}</span>
                </div>
            </div>

            <div class="idea-potential-row">
                <div class="potential-gauge">
                    <span class="potential-label">📈 Traffic</span>
                    <div class="potential-bar-track"><div class="potential-bar-fill ${trafficLevel}" style="width: ${trafficPercent}%"></div></div>
                    <span class="potential-value ${trafficLevel}">${idea.traffic_potential || '—'}</span>
                </div>
                <div class="potential-gauge">
                    <span class="potential-label">💵 Revenue</span>
                    <div class="potential-bar-track"><div class="potential-bar-fill ${revenueLevel}" style="width: ${revenuePercent}%"></div></div>
                    <span class="potential-value ${revenueLevel}">${idea.revenue_potential || '—'}</span>
                </div>
            </div>

            <div class="idea-expandable">
                ${techPills ? `
                    <div class="idea-section">
                        <div class="idea-section-label">⚙️ Tech Stack</div>
                        <div class="tech-pills-container">${techPills}</div>
                    </div>
                ` : ''}

                ${mvpHtml ? `
                    <div class="idea-section">
                        <div class="idea-section-label">🚀 MVP Features</div>
                        <ul class="idea-mvp-list-v2">${mvpHtml}</ul>
                    </div>
                ` : ''}
            </div>

            <div class="idea-footer-v2">
                <span class="idea-source-v2">
                    <span class="platform-badge ${idea.platform}" style="font-size: 0.65rem; padding: 2px 8px;">${idea.platform}</span>
                    <a href="${escapeHtml(idea.post_url || '#')}" target="_blank" rel="noopener" class="idea-source-link" onclick="event.stopPropagation()">
                        ${escapeHtml(truncate(idea.post_title, 50))}
                    </a>
                </span>
                <span class="expand-hint">Click to expand</span>
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
                    <div class="section-title">Scrape Pipeline</div>
                    <div class="section-subtitle">Scrape platforms, analyze problems, and generate app ideas</div>
                </div>
            </div>

            <div class="glass-card" style="padding: 28px; margin-bottom: 24px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                    <span style="font-size: 1.5rem;">⚡</span>
                    <div>
                        <div style="font-weight: 700; font-size: 1rem;">Run Pipeline</div>
                        <div style="font-size: 0.82rem; color: var(--text-tertiary);">Select a platform or scrape all enabled platforms</div>
                    </div>
                </div>

                <div class="scrape-controls">
                    <div class="form-group">
                        <label class="form-label">Platform</label>
                        <select class="form-select" id="scrapePlatform">
                            <option value="">All Platforms</option>
                            <option value="reddit">Reddit</option>
                            <option value="hackernews">Hacker News</option>
                            <option value="producthunt">Product Hunt</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Limit</label>
                        <input type="number" class="form-input" id="scrapeLimit" placeholder="Default" min="1" max="200" style="width: 120px;">
                    </div>
                    <button class="btn btn-primary" id="scrapeBtn" ${isRunning ? 'disabled' : ''}>
                        ${isRunning ? '⏳ Running...' : '🚀 Start Scraping'}
                    </button>
                </div>
            </div>

            <div id="scrapeStatus">
                ${isRunning ? renderScrapeRunning() : ''}
                ${status && status.result ? renderScrapeResult(status.result) : ''}
                ${status && status.error ? renderScrapeError(status.error) : ''}
            </div>

            <div class="glass-card">
                <div class="card-header">
                    <div class="section-title">Pipeline Flow</div>
                </div>
                <div class="card-body" style="padding: 24px;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                        ${renderPipelineStep('1', 'Scrape', 'Fetch posts from Reddit, HN, Product Hunt', '🌐')}
                        ${renderPipelineStep('2', 'Filter', 'AI-score each post for pain signals', '🔍')}
                        ${renderPipelineStep('3', 'Analyze', 'Deep analysis of high-potential problems', '🧠')}
                        ${renderPipelineStep('4', 'Generate', 'Create app ideas from validated problems', '💡')}
                    </div>
                </div>
            </div>
        </div>
    `;

    // Bind scrape button
    document.getElementById('scrapeBtn').addEventListener('click', startScrape);

    if (isRunning) {
        startScrapePolling();
    }
}

function renderPipelineStep(num, title, desc, icon) {
    return `
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-primary); border-radius: var(--radius-sm); padding: 18px; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 10px;">${icon}</div>
            <div style="font-size: 0.7rem; color: var(--purple); font-weight: 700; letter-spacing: 0.1em; margin-bottom: 4px;">STEP ${num}</div>
            <div style="font-weight: 700; margin-bottom: 4px;">${title}</div>
            <div style="font-size: 0.8rem; color: var(--text-tertiary); line-height: 1.4;">${desc}</div>
        </div>
    `;
}

function renderScrapeRunning() {
    return `
        <div class="scrape-progress">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <div class="spinner" style="width: 20px; height: 20px; border-width: 2px;"></div>
                <span style="font-weight: 600;">Pipeline is running...</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" style="width: 60%;"></div>
            </div>
            <div class="progress-text">Scraping platforms and analyzing posts. This may take a few minutes.</div>
        </div>
    `;
}

function renderScrapeResult(result) {
    return `
        <div class="glass-card" style="margin-bottom: 24px; border-color: rgba(16, 185, 129, 0.3);">
            <div style="padding: 22px;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                    <span style="font-size: 1.3rem;">✅</span>
                    <span style="font-weight: 700; color: var(--emerald);">Pipeline Completed</span>
                </div>
                <div class="stats-grid" style="margin-bottom: 0;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--purple);">${result.scraped || 0}</div>
                        <div style="font-size: 0.78rem; color: var(--text-tertiary);">Posts Scraped</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--cyan);">${result.high_potential || 0}</div>
                        <div style="font-size: 0.78rem; color: var(--text-tertiary);">High Potential</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--emerald);">${result.insights || 0}</div>
                        <div style="font-size: 0.78rem; color: var(--text-tertiary);">Insights</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--amber);">${result.app_ideas || 0}</div>
                        <div style="font-size: 0.78rem; color: var(--text-tertiary);">App Ideas</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderScrapeError(error) {
    return `
        <div class="glass-card" style="margin-bottom: 24px; border-color: rgba(244, 63, 94, 0.3);">
            <div style="padding: 22px;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <span style="font-size: 1.3rem;">❌</span>
                    <span style="font-weight: 700; color: var(--rose);">Pipeline Error</span>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); font-family: monospace; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px;">${escapeHtml(error)}</div>
            </div>
        </div>
    `;
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
    btn.innerHTML = '⏳ Starting...';

    try {
        await apiPost(endpoint);
        statusDiv.innerHTML = renderScrapeRunning();
        btn.innerHTML = '⏳ Running...';
        updateStatusIndicator(true);
        startScrapePolling();
    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = '🚀 Start Scraping';
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

            // Refresh page
            if (currentPage === 'scrape') {
                renderScrape(document.getElementById('pageContent'));
            }
        }
    }, 3000);
}

function updateStatusIndicator(scraping) {
    const dot = document.querySelector('.status-dot');
    const text = document.querySelector('.status-text');
    if (scraping) {
        dot.classList.add('scraping');
        text.textContent = 'Scraping...';
    } else {
        dot.classList.remove('scraping');
        text.textContent = 'Ready';
    }
}

// ── Runs Page ──────────────────────────────────────────────────────
async function renderRuns(container) {
    const runs = await apiGet('/api/runs');

    container.innerHTML = `
        <div class="fade-in">
            <div class="section-header" style="margin-bottom: 20px;">
                <div>
                    <div class="section-title">Run History</div>
                    <div class="section-subtitle">Past pipeline executions</div>
                </div>
            </div>
            <div class="glass-card">
                <div class="card-body">
                    ${(runs || []).length > 0 ? `
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Started</th>
                                    <th>Platform</th>
                                    <th>Posts</th>
                                    <th>Problems</th>
                                    <th>Duration</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(runs || []).map(run => `
                                    <tr>
                                        <td style="color: var(--text-muted);">${run.id}</td>
                                        <td>${formatDate(run.started_at)}</td>
                                        <td>${(run.platform || '').split(',').map(p => `<span class="platform-badge ${p.trim()}" style="font-size: 0.65rem; padding: 2px 7px;">${p.trim()}</span>`).join(' ')}</td>
                                        <td>${run.posts_scraped || 0}</td>
                                        <td>${run.problems_found || 0}</td>
                                        <td>${run.duration_seconds ? run.duration_seconds.toFixed(1) + 's' : '—'}</td>
                                        <td><span class="run-status ${run.status || ''}">${run.status || 'unknown'}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    ` : `
                        <div class="empty-state">
                            <div class="empty-state-icon">🕐</div>
                            <div class="empty-state-title">No runs yet</div>
                            <div class="empty-state-text">Start your first scrape to see the run history here.</div>
                            <a href="#scrape" class="btn btn-primary">Start Scraping →</a>
                        </div>
                    `}
                </div>
            </div>
        </div>
    `;
}

// ── Utility Functions ──────────────────────────────────────────────
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.slice(0, max) + '…' : str;
}

function formatNumber(num) {
    if (num == null) return '0';
    return Number(num).toLocaleString();
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
        return dateStr;
    }
}

function platformIcon(platform) {
    const icons = {
        reddit: '◉',
        hackernews: '▲',
        producthunt: '🚀',
    };
    return icons[platform] || '●';
}

function scoreClass(val, highThreshold, medThreshold) {
    if (val == null) return 'low';
    if (val >= highThreshold) return 'high';
    if (val >= medThreshold) return 'medium';
    return 'low';
}

function potentialClass(level) {
    if (!level) return 'low';
    const l = level.toLowerCase();
    if (l.includes('high') || l.includes('yüksek')) return 'high';
    if (l.includes('medium') || l.includes('orta')) return 'medium';
    return 'low';
}

function getIdeaTypeClass(type) {
    if (!type) return 'default';
    const t = type.toLowerCase();
    if (t.includes('web')) return 'web';
    if (t.includes('mobile')) return 'mobile';
    if (t.includes('saas')) return 'saas';
    if (t.includes('extension') || t.includes('plugin')) return 'extension';
    return 'default';
}

// ── Sidebar toggle (mobile) ───────────────────────────────────────
function initSidebar() {
    const toggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');

    toggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // Close sidebar when clicking a nav item on mobile
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
            }
        });
    });
}

// ── Init ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initRouter();
});
