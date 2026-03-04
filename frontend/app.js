document.addEventListener('DOMContentLoaded', () => {
    // --- State ---
    const state = {
        assets: {
            actors: [],
            clothes: [],
            scenes: []
        },
        currentTab: 'dashboard'
    };

    // --- DOM Elements ---
    const navItems = document.querySelectorAll('.nav-links li');
    const pageTitle = document.getElementById('page-title');

    // Views
    const dashboardView = document.getElementById('dashboard-view');
    const actorsView = document.getElementById('actors-view');
    const clothesView = document.getElementById('clothes-view');
    const scenesView = document.getElementById('scenes-view');

    // Grids & Stats
    const grids = {
        clothes: document.getElementById('grid-clothes'),
        scenes: document.getElementById('grid-scenes')
    };

    const recentActors = document.getElementById('recent-actors');
    const recentClothes = document.getElementById('recent-clothes');

    // Modals
    const btnGenerate = document.getElementById('btn-generate');
    const generateModal = document.getElementById('generate-modal');
    const btnCancel = document.getElementById('btn-cancel');

    // Import Modal
    const btnImportLink = document.getElementById('btn-import-link');
    const modalImportLink = document.getElementById('modal-import-link');
    const btnDoImport = document.getElementById('btn-do-import');
    const importUrlInput = document.getElementById('import-url-input');
    const importStatus = document.getElementById('import-status');

    // --- Initialization moved to bottom ---

    async function init() {
        setupEventListeners();
        await fetchAssets();
        render();
    }

    // --- Data Fetching ---
    async function fetchAssets() {
        try {
            const response = await fetch('/api/assets');
            const data = await response.json();
            // Data structure: { actors: [...], clothes: [...], scenes: [...] }
            state.assets = data;
        } catch (error) {
            console.error("Failed to fetch assets:", error);
            // Fallback mock data for visual demonstration
            state.assets = {
                actors: [
                    { id: 'frame_0001_female_model', url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80', date: '2026-02-25' },
                    { id: 'frame_0010_male_model', url: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80', date: '2026-02-25' }
                ],
                clothes: [
                    { id: 'frame_0005_leather_jacket', url: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80', date: '2026-02-25' },
                    { id: 'frame_0020_white_shirt', url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80', date: '2026-02-25' }
                ],
                scenes: [
                    { id: 'frame_0003_cafe_background', url: 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80', date: '2026-02-25' }
                ]
            };
        }
    }

    // --- Renderers ---
    function render() {
        if (state.currentTab === 'dashboard') {
            renderDashboard();
        } else if (state.currentTab === 'clothes') {
            // Table rendered directly
        } else if (state.currentTab === 'scenes') {
            renderGrid(grids.scenes, state.assets.scenes, 'scenes');
        }
        updateStats();
    }

    function updateStats() {
        // Stats removed
    }

    function createCardHTML(asset) {
        // Humanize the ID
        const title = asset.id.replace(/_/g, ' ').replace('frame', '').trim();
        return `
            <div class="asset-card">
                <div class="asset-img-container">
                    <img src="${asset.url}" alt="${title}" loading="lazy" onerror="this.src='https://via.placeholder.com/400x600?text=Preview'">
                </div>
                <div class="asset-info">
                    <p>${title || 'Extracted Asset'}</p>
                    <p class="date">${asset.date}</p>
                </div>
            </div>
        `;
    }

    async function renderDashboard() {
        const dashboardContainer = document.getElementById('dashboard-view');
        dashboardContainer.innerHTML = '<div style="padding:2rem; color:var(--text-secondary)">Loading premium feed...</div>';

        try {
            const res = await fetch('/api/posts');
            const { posts } = await res.json();

            if (!posts || posts.length === 0) {
                dashboardContainer.innerHTML = `
                    <div style="text-align:center; padding: 4rem 0;">
                        <h3 style="color:white; margin-bottom:1rem">No assets found</h3>
                        <p style="color:var(--text-secondary)">Import a link to see your resources here.</p>
                    </div>
                `;
                return;
            }

            dashboardContainer.innerHTML = `
                <div class="dashboard-sections" style="padding-bottom: 4rem;">
                    ${posts.reverse().map(p => {
                let dateStr = 'Unknown Date';
                if (p.updated_at) {
                    try { dateStr = new Date(p.updated_at).toLocaleDateString(); } catch (e) { }
                } else if (p.date) {
                    dateStr = p.date;
                }

                // Collect child assets for this post
                const children = [];
                (p.actors_info || []).forEach(a => children.push({ ...a, type: 'actors', url: a.cutout_url, id: a.actor_id }));
                (p.clothes_info || []).forEach(c => children.push({ ...c, type: 'clothes', url: c.render_url, id: c.clothes_id }));
                (p.scenes_info || []).forEach(s => children.push({ ...s, type: 'scenes', url: s.scene_url, id: s.scene_id }));

                return `
                        <div class="post-unit" style="background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 16px; margin-bottom: 2rem; overflow: hidden;">
                            <div class="post-header" style="padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02);">
                                <div>
                                    <h3 style="margin: 0; color: white; display:flex; align-items:center; gap:0.5rem;">
                                        <i class="fas fa-link" style="color:var(--accent); font-size:0.9rem;"></i> 
                                        <a href="${p.source_url || '#'}" target="_blank" style="color: white; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">${p.topic || 'Imported Link'}</a>
                                    </h3>
                                    <span style="font-size: 0.8rem; color: var(--text-secondary);">${dateStr}</span>
                                </div>
                                <button class="btn-secondary" onclick="openVideoDetailModal('${p.post_id}')" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">View Intelligence</button>
                            </div>
                            <div class="post-body" style="display: flex; flex-wrap: wrap; padding: 1.5rem; gap: 1.5rem;">
                                
                                <!-- Main Video/Thumbnail -->
                                <div class="post-main-media" style="flex: 0 0 300px; max-width: 100%;">
                                    <div class="video-window" id="window-${p.post_id}" onclick="window.toggleInPlacePlay('${p.post_id}')" style="margin-bottom: 0; width: 100%;">
                                        ${p.thumbnail_url ? `<img src="${p.thumbnail_url}" alt="thumbnail" onerror="this.src='https://via.placeholder.com/800x450?text=Preview'">` : `<div style="height:168px; display:flex; align-items:center; justify-content:center; background:var(--bg-main); color:var(--text-secondary)">No Thumbnail</div>`}
                                        ${p.video_url ? `
                                            <video class="preview-video" loop muted playsinline src="${p.video_url}"></video>
                                            <div class="play-btn"><i class="fas fa-play">▶</i></div>
                                        ` : ''}
                                        <div class="info-btn" onclick="event.stopPropagation(); openVideoDetailModal('${p.post_id}')"><i class="fas fa-info-circle">i</i></div>
                                        <div class="window-info" style="padding: 1.5rem 1rem 0.5rem;"><h4 style="font-size:0.8rem;">Source Media</h4></div>
                                    </div>
                                </div>

                                <!-- Extracted Assets Gallery -->
                                <div class="post-assets" style="flex: 1; min-width: 300px;">
                                    <h4 style="margin-bottom: 1rem; color: var(--text-secondary); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">Extracted Assets (${children.length})</h4>
                                    ${children.length > 0 ? `
                                        <div class="gallery-grid" style="grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 0.8rem;">
                                            ${children.map(child => `
                                                <div class="asset-card" onclick="openEntityDetail('${child.type}', '${child.id}')" style="border-radius: 8px;">
                                                    <div class="asset-img-container" style="padding: 6px;">
                                                        <img src="${child.url}" alt="${child.display_name || 'Asset'}" loading="lazy" onerror="this.src='https://via.placeholder.com/400x600?text=Asset'">
                                                    </div>
                                                    <div class="asset-info" style="padding: 0.5rem;">
                                                        <p style="font-size: 0.75rem;">${child.display_name || humanize(child.id)}</p>
                                                        <p class="date" style="font-size: 0.65rem; text-transform: capitalize;">${child.type.slice(0, -1)}</p>
                                                    </div>
                                                </div>
                                            `).join('')}
                                        </div>
                                    ` : '<p style="color:var(--text-secondary); font-size: 0.9rem;">No entities extracted for this link yet.</p>'}
                                </div>
                            </div>
                        </div>
                        `;
            }).join('')}
                </div>
            `;

        } catch (err) {
            console.error("Dashboard render failed:", err);
            dashboardContainer.innerHTML = '<p style="color:#ff6b6b; padding:2rem;">Failed to load dashboard data.</p>';
        }
    }

    // Helper for Apple-style in-place play
    window.toggleInPlacePlay = (postId) => {
        console.log(`[Interaction] Card click: toggling play for ${postId}`);
        const container = document.getElementById(`window-${postId}`);
        if (!container) return;

        const video = container.querySelector('video');
        if (!video) {
            console.warn(`[Playback] No video found for post ${postId} (may be an image gallery)`);
            return;
        }

        console.log(`[Playback] Toggling playback for ${postId}. Current src: ${video.src}`);

        if (container.classList.contains('playing')) {
            video.pause();
            container.classList.remove('playing');
        } else {
            // Stop other playing videos
            document.querySelectorAll('.video-window.playing').forEach(win => {
                win.querySelector('video')?.pause();
                win.classList.remove('playing');
            });

            const playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    console.log(`[Playback] Success: ${postId}`);
                    container.classList.add('playing');
                }).catch(error => {
                    console.error(`[Playback] Error:`, error);
                    alert("Video playback failed. Check if the source exists or if browser policies block auto-play.");
                });
            }
        }
    };

    function humanize(text) {
        if (!text) return '';
        // Remove common patterns: image_001_, time_0000.00s_, frame_0001_
        return text
            .replace(/^(image|frame)_\d{3,4}_/i, '')
            .replace(/^time_[\d\.]+s_/i, '')
            .replace(/_/g, ' ')
            .trim();
    }

    function createCardHTML(asset) {
        const title = humanize(asset.id);
        const type = asset.url.includes('/clothes/') ? 'clothes' : (asset.url.includes('/actors/') ? 'actors' : 'scenes');

        let dateStr = '';
        if (asset.created_at) {
            try {
                dateStr = new Date(asset.created_at).toLocaleString();
            } catch (e) { }
        }

        return `
            <div class="asset-card" onclick="openEntityDetail('${type}', '${asset.id}')">
                <div class="asset-img-container">
                    <img src="${asset.url}" alt="${title}" loading="lazy" onerror="this.src='https://via.placeholder.com/400x600?text=Preview'">
                </div>
                <div class="asset-info">
                    <p>${title || 'Extracted Asset'}</p>
                    <p class="date" style="font-size: 0.8em; color: #888; margin-top: 4px;">${dateStr}</p>
                </div>
            </div>
        `;
    }

    // --- Navigation ---
    const kbView = document.getElementById('kb-view');

    function switchTab(tabId) {
        state.currentTab = tabId;

        navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.tab === tabId);
        });

        const titles = {
            'dashboard': 'Resource Dashboard',
            'kb': 'Knowledge Base',
            'actors': 'Virtual Actors Library',
            'clothes': 'Clothing Vault',
            'scenes': 'Scene Library'
        };
        pageTitle.textContent = titles[tabId] || tabId;

        // Hide all views
        [dashboardView, actorsView, clothesView, scenesView, kbView].forEach(v => v && v.classList.add('hidden'));

        const searchContainer = document.getElementById('search-container');
        searchContainer.classList.add('hidden');

        if (tabId === 'dashboard') {
            dashboardView.classList.remove('hidden');
        } else if (tabId === 'kb') {
            kbView.classList.remove('hidden');
            fetchKB('posts');
        } else if (tabId === 'clothes') {
            clothesView.classList.remove('hidden');
            searchContainer.classList.remove('hidden');
            const searchInput = document.getElementById('semantic-search-input');
            if (searchInput) { searchInput.placeholder = `Search within ${titles[tabId]}...`; searchInput.value = ''; }
            renderClothesTable();
        } else {
            const viewMap = { actors: actorsView, scenes: scenesView };
            viewMap[tabId]?.classList.remove('hidden');
            searchContainer.classList.remove('hidden');
            const searchInput = document.getElementById('semantic-search-input');
            if (searchInput) { searchInput.placeholder = `Search within ${titles[tabId]}...`; searchInput.value = ''; }
        }

        render();
    }

    // ─── Knowledge Base ───────────────────────────────────────────────────────
    let kbCurrentFilter = 'posts';

    async function fetchKB(filter = 'posts') {
        kbCurrentFilter = filter;
        document.querySelectorAll('.kb-filter-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.filter === filter);
        });

        const tbody = document.getElementById('kb-tbody');
        const thead = document.getElementById('kb-thead');
        const empty = document.getElementById('kb-empty');
        const countEl = document.getElementById('kb-count');
        tbody.innerHTML = '<tr><td colspan="10" style="padding:2rem;text-align:center;color:var(--text-secondary)">Loading...</td></tr>';

        try {
            if (filter === 'posts') {
                const res = await fetch('/api/posts');
                const { posts } = await res.json();
                countEl.textContent = `${posts.length} posts`;
                if (!posts.length) { empty.classList.remove('hidden'); tbody.innerHTML = ''; return; }
                empty.classList.add('hidden');

                thead.innerHTML = `<tr>
                    <th>Post</th><th>Date</th><th>Actors</th><th>Clothes</th><th>Topic</th><th>Transcript</th>
                </tr>`;
                tbody.innerHTML = posts.reverse().map(p => `
                    <tr data-post-id="${p.post_id}">
                        <td class="kb-thumb-cell">
                            ${p.thumbnail_url ? `<img class="kb-thumbnail" src="${p.thumbnail_url}" onerror="this.style.display='none'">` : ''}
                            <div class="kb-post-meta">
                                <span class="kb-post-title">${p.topic || p.post_id.substring(0, 10)}</span>
                                <span class="kb-post-date">${p.date}</span>
                            </div>
                        </td>
                        <td style="color:var(--text-secondary);font-size:0.82rem">${p.date}</td>
                        <td><div class="entity-chips">${(p.actors_info || []).map(a =>
                    `<span class="entity-chip${a.celebrity_name ? ' celebrity' : ''}" data-entity-type="actors" data-entity-id="${a.actor_id}">${a.display_name}</span>`
                ).join('')}</div></td>
                        <td><div class="entity-chips">${(p.clothes_info || []).map(c =>
                    `<span class="entity-chip clothes" data-entity-type="clothes" data-entity-id="${c.clothes_id}">${c.color} ${c.category}</span>`
                ).join('')}</div></td>
                        <td>${p.topic ? `<span class="kb-topic-badge">${p.topic}</span>` : '—'}</td>
                        <td style="color:var(--text-secondary);font-size:0.8rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.transcript?.substring(0, 80) || '—'}</td>
                    </tr>
                `).join('');

            } else {
                const res = await fetch(`/api/entities/${filter}`);
                const { entities } = await res.json();
                countEl.textContent = `${entities.length} ${filter}`;
                if (!entities.length) { empty.classList.remove('hidden'); tbody.innerHTML = ''; return; }
                empty.classList.add('hidden');

                if (filter === 'actors') {
                    thead.innerHTML = `<tr><th>Preview</th><th>Name / Style</th><th>Celebrity</th><th>Posts</th></tr>`;
                    tbody.innerHTML = entities.map(a => `
                        <tr data-entity-type="actors" data-entity-id="${a.actor_id}">
                            <td>${a.cutout_url ? `<img class="kb-thumbnail" src="${a.cutout_url}" style="background:transparent">` : '—'}</td>
                            <td><strong>${a.display_name}</strong><br><small style="color:var(--text-secondary)">${a.style_class}</small></td>
                            <td>${a.celebrity_name ? `<span class="entity-chip celebrity">${a.celebrity_name}</span>` : '—'}</td>
                            <td>${a.appeared_in?.length || 0}</td>
                        </tr>`).join('');
                } else if (filter === 'clothes') {
                    thead.innerHTML = `<tr><th>Render</th><th>Color</th><th>Category</th><th>Style</th><th>Posts</th></tr>`;
                    tbody.innerHTML = entities.map(c => `
                        <tr data-entity-type="clothes" data-entity-id="${c.clothes_id}">
                            <td>${c.render_url ? `<img class="kb-thumbnail" src="${c.render_url}" style="background:transparent">` : '—'}</td>
                            <td>${c.color}</td>
                            <td>${c.category}</td>
                            <td><span class="entity-chip clothes">${c.style_class}</span></td>
                            <td>${c.appeared_in?.length || 0}</td>
                        </tr>`).join('');
                }
            }

            // Click handlers: entity chip → entity detail, row → open post or entity
            document.querySelectorAll('[data-entity-type]').forEach(el => {
                el.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await openEntityDetail(el.dataset.entityType, el.dataset.entityId);
                });
            });
            document.querySelectorAll('#kb-tbody tr[data-post-id]').forEach(row => {
                row.addEventListener('click', () => {
                    // Navigate to post detail (using existing video detail modal)
                    openVideoDetailModal(row.dataset.postId);
                });
            });

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="10" style="padding:2rem;text-align:center;color:#ff6b6b">Failed to load data: ${err.message}</td></tr>`;
        }
    }

    // --- Entity Detail Modal ---
    window.openEntityDetail = async function (type, id) {
        const modal = document.getElementById('modal-entity-detail');
        const title = document.getElementById('entity-detail-title');
        const body = document.getElementById('entity-detail-body');
        modal.classList.remove('hidden');
        body.innerHTML = '<p style="color:var(--text-secondary)">Loading...</p>';

        try {
            const res = await fetch(`/api/entities/${type}/${id}`);
            const entity = await res.json();

            const imgUrl = entity.cutout_url || entity.render_url || entity.scene_url || '';
            const label = entity.display_name || entity.description || id;
            title.textContent = type === 'clothes' ? 'Edit Product Entity' : label;

            const postsHTML = (entity.posts || []).map(p => `
                <div class="entity-post-card" onclick="document.getElementById('modal-entity-detail').classList.add('hidden'); openVideoDetailModal('${p.post_id}')">
                    <div style="font-weight:600;margin-bottom:4px">${p.topic || p.post_id.substring(0, 12)}</div>
                    <div style="color:var(--text-secondary);font-size:0.75rem">${p.date}</div>
                </div>`).join('');

            if (type === 'clothes') {
                // Interactive Edit Form for Products
                body.innerHTML = `
                    <div style="display:flex; gap: 2rem; align-items: flex-start; margin-bottom: 2rem;">
                        ${imgUrl ? `<img src="${imgUrl}" style="width:200px; height:200px; object-fit:contain; background:var(--bg-panel); border-radius:12px; border:1px solid var(--border-color);">` : ''}
                        
                        <div style="flex:1; display:flex; flex-direction:column; gap:1rem;">
                            <div>
                                <label style="display:block; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">Product Name</label>
                                <input type="text" id="edit-clothes-name" value="${entity.display_name || ''}" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--border-color); background:var(--bg-main); color:white;">
                            </div>
                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem;">
                                <div>
                                    <label style="display:block; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">Category</label>
                                    <input type="text" id="edit-clothes-category" value="${entity.category || ''}" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--border-color); background:var(--bg-main); color:white;">
                                </div>
                                <div>
                                    <label style="display:block; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">Color</label>
                                    <input type="text" id="edit-clothes-color" value="${entity.color || ''}" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--border-color); background:var(--bg-main); color:white;">
                                </div>
                            </div>
                            <div>
                                <label style="display:block; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">Style Class</label>
                                <input type="text" id="edit-clothes-style" value="${entity.style_class || ''}" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--border-color); background:var(--bg-main); color:white;">
                            </div>
                            
                            ${entity.attributes && Object.keys(entity.attributes).length > 0 ? `
                            <div style="margin-top: 0.5rem; background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                                <h4 style="margin-bottom: 0.8rem; color: var(--accent); font-size: 0.9rem;">Product Parameters</h4>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.85rem;">
                                    ${Object.entries(entity.attributes).map(([k, v]) => `
                                        <div style="color: var(--text-secondary);">${k}:</div>
                                        <div style="color: white; font-weight: 500;">${v}</div>
                                    `).join('')}
                                </div>
                            </div>
                            ` : ''}
                        </div>
                    </div>

                    ${entity.gallery_urls?.length > 1 ? `
                    <h4 style="margin-bottom:1rem; color:white;">Product Gallery (${entity.gallery_urls.length} images)</h4>
                    <div class="gallery-grid" style="grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.5rem; margin-bottom: 2rem;">
                        ${entity.gallery_urls.map(url => `
                            <div class="asset-card" style="border-radius: 6px; cursor:zoom-in;">
                                <div class="asset-img-container" style="padding: 4px;">
                                    <img src="${url}" style="border-radius: 4px;" loading="lazy">
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    ` : ''}
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-color); padding-top:1.5rem; margin-bottom:1.5rem;">
                        <button id="btn-delete-clothes" style="padding:10px 16px; background:#ff475722; color:#ff4757; border:1px solid #ff475755; border-radius:6px; cursor:pointer;" onclick="deleteClothesEntity('${id}')">
                            <i class="fas fa-trash"></i> Delete Product
                        </button>
                        <button id="btn-save-clothes" class="btn-primary" onclick="updateClothesEntity('${id}')">
                            Save Changes
                        </button>
                    </div>

                    ${entity.posts?.length ? `<h4 style="margin-bottom:0.5rem;color:white">Source Videos (${entity.posts.length})</h4>
                    <div class="entity-posts-grid">${postsHTML}</div>` : ''}

                    ${entity.source_keyframe ? `
                    <h4 style="margin-top:2rem; margin-bottom:0.5rem; color:white;">Source Keyframe</h4>
                    <img src="${entity.source_keyframe}" style="width:100%; max-height:300px; object-fit:contain; border-radius:12px; border:1px solid var(--border-color); background:var(--bg-main); cursor:zoom-in;">
                    ` : ''}
                `;
            } else {
                // Static read-only view for Actors and Scenes
                body.innerHTML = `
                    ${imgUrl ? `<img class="entity-preview" src="${imgUrl}" style="background:transparent;max-height:260px;object-fit:contain">` : ''}
                    <div style="margin-bottom:0.5rem">
                        ${entity.celebrity_name ? `<span class="entity-chip celebrity" style="margin-right:0.5rem">⭐ ${entity.celebrity_name}</span>` : ''}
                        ${entity.style_class ? `<span class="entity-chip">${entity.style_class}</span>` : ''}
                        ${entity.category ? `<span class="entity-chip clothes" style="margin-left:0.4rem">${entity.category}</span>` : ''}
                    </div>
                    <p style="color:var(--text-secondary);margin:0.75rem 0;font-size:0.9rem">${entity.description || ''}</p>
                    ${entity.posts?.length ? `<h4 style="margin-bottom:0.5rem;color:white">Appeared in ${entity.posts.length} post(s)</h4>
                    <div class="entity-posts-grid">${postsHTML}</div>` : '<p style="color:var(--text-secondary)">No posts linked yet.</p>'}
                `;
            }
        } catch (err) {
            body.innerHTML = `<p style="color:#ff6b6b">Failed to load entity: ${err.message}</p>`;
        }
    }

    // Handlers for clothes CRUD
    window.updateClothesEntity = async function (id) {
        const btn = document.getElementById('btn-save-clothes');
        const originalText = btn.textContent;
        btn.textContent = 'Saving...';
        btn.disabled = true;

        const updates = {
            display_name: document.getElementById('edit-clothes-name').value,
            category: document.getElementById('edit-clothes-category').value,
            color: document.getElementById('edit-clothes-color').value,
            style_class: document.getElementById('edit-clothes-style').value
        };

        try {
            const res = await fetch(`/api/entities/clothes/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            if (!res.ok) throw new Error('Update failed');

            // Refresh table if active
            if (state.currentTab === 'clothes') renderClothesTable();
            document.getElementById('modal-entity-detail').classList.add('hidden');
        } catch (err) {
            alert("Failed to save changes: " + err.message);
            btn.textContent = originalText;
            btn.disabled = false;
        }
    };

    window.deleteClothesEntity = async function (id) {
        if (!confirm("Are you sure you want to delete this product? This will remove it from the knowledge base.")) return;

        try {
            const res = await fetch(`/api/entities/clothes/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Delete failed');

            if (state.currentTab === 'clothes') renderClothesTable();
            document.getElementById('modal-entity-detail').classList.add('hidden');
        } catch (err) {
            alert("Failed to delete: " + err.message);
        }
    };

    // --- Search ---
    async function handleSearch() {
        const query = document.getElementById('semantic-search-input').value.trim();
        const category = state.currentTab;

        if (!query || category === 'dashboard') {
            renderGrid(category); // reset to normal grid
            return;
        }

        const grid = grids[category];
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 3rem;">Scanning vector space...</div>';

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, query, top_k: 10 })
            });

            const data = await response.json();
            const results = data.results || [];

            if (results.length === 0) {
                grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 3rem;">No semantically matching assets found.</div>';
                return;
            }

            // Render search results mapping description to card
            grid.innerHTML = results.map(asset => {
                // Asset from search has 'id', 'url', 'description'
                const title = asset.id.replace(/_/g, ' ').replace('frame', '').trim();
                return `
                    <div class="asset-card">
                        <div class="asset-img-container">
                            <img src="${asset.url}" alt="${title}" loading="lazy" onerror="this.src='https://via.placeholder.com/400x600?text=Preview'">
                        </div>
                        <div class="asset-info" style="height: auto; padding-top: 2rem;">
                            <p style="white-space: normal; line-height: 1.3;">${asset.description}</p>
                            <p class="date">Similarity Match</p>
                        </div>
                    </div>
                `;
            }).join('');

        } catch (error) {
            console.error("Search failed:", error);
            grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #ff6b6b; padding: 3rem;">Search failed. Is the vector database running?</div>';
        }
    }

    async function renderClothesTable() {
        const tbody = document.getElementById('clothes-tbody');
        const empty = document.getElementById('clothes-empty');
        const countEl = document.getElementById('clothes-table-count');
        tbody.innerHTML = '<tr><td colspan="7" style="padding:2rem;text-align:center;color:var(--text-secondary)">Loading product spreadhseet...</td></tr>';

        try {
            const res = await fetch('/api/entities/clothes');
            const { entities } = await res.json();
            countEl.textContent = `${entities.length} items`;

            if (!entities.length) {
                empty.classList.remove('hidden');
                tbody.innerHTML = '';
                return;
            }
            empty.classList.add('hidden');

            tbody.innerHTML = entities.reverse().map(c => `
                <tr data-entity-type="clothes" data-entity-id="${c.clothes_id}">
                    <td class="kb-thumb-cell">
                        ${c.render_url ? `<img class="kb-thumbnail" src="${c.render_url}" style="background:transparent; cursor:zoom-in" onclick="event.stopPropagation()">` : '<div style="width:60px;height:60px;background:var(--bg-panel);border-radius:6px"></div>'}
                    </td>
                    <td style="font-family:monospace; font-size:0.8rem; color:var(--text-secondary)">${c.clothes_id.substring(0, 8)}</td>
                    <td style="font-weight:600; cursor:pointer" onclick="openEntityDetail('clothes', '${c.clothes_id}')">
                        ${c.display_name} <i class="fas fa-edit" style="color:var(--text-secondary); margin-left:8px; font-size:0.8rem"></i>
                    </td>
                    <td>${c.category}</td>
                    <td><span class="entity-chip clothes">${c.style_class}</span></td>
                    <td>${c.color}</td>
                    <td style="color:var(--accent); font-weight:600; cursor:pointer" onclick="event.stopPropagation(); openEntityDetail('clothes', '${c.clothes_id}')">
                        <i class="fas fa-images"></i> ${c.gallery_urls?.length || 1} 张
                    </td>
                    <td>${c.appeared_in?.length || 0}</td>
                </tr>
            `).join('');

            // Add click row listener to edit product
            document.querySelectorAll('#clothes-tbody tr[data-entity-type="clothes"]').forEach(row => {
                row.addEventListener('click', () => {
                    openEntityDetail('clothes', row.dataset.entityId);
                });
            });

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="7" style="padding:2rem;text-align:center;color:#ff6b6b">Failed to load products: ${err.message}</td></tr>`;
        }
    }

    // --- Event Listeners ---
    function setupEventListeners() {
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                switchTab(item.dataset.tab);
            });
        });

        document.querySelectorAll('.view-all').forEach(btn => {
            btn.addEventListener('click', (e) => {
                switchTab(e.target.dataset.target);
            });
        });

        // Search Bindings
        document.getElementById('btn-search').addEventListener('click', handleSearch);
        document.getElementById('semantic-search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSearch();
        });

        // Knowledge Base filter buttons
        document.querySelectorAll('.kb-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => fetchKB(btn.dataset.filter));
        });

        // Delegate click events on images to open Video Detail Modal
        document.body.addEventListener('click', async (e) => {
            const card = e.target.closest('.asset-card');
            if (card && card.dataset.videoId) {
                await openVideoDetailModal(card.dataset.videoId);
            }
        });

        // Generate modal
        btnGenerate.addEventListener('click', () => {
            generateModal.classList.remove('hidden');
        });
        btnCancel.addEventListener('click', () => {
            generateModal.classList.add('hidden');
        });
        generateModal.addEventListener('click', (e) => {
            if (e.target === generateModal) generateModal.classList.add('hidden');
        });

        // Bottom Tab Bar Navigation (mobile)
        document.querySelectorAll('.bottom-tab-bar .tab-item[data-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.dataset.tab;
                // Handle special "search-tab" by switching to dashboard + focusing search
                if (tabId === 'search-tab') {
                    switchTab('dashboard');
                    const searchContainer = document.getElementById('search-container');
                    searchContainer.classList.remove('hidden');
                    document.getElementById('semantic-search-input')?.focus();
                } else {
                    switchTab(tabId);
                }
                // Update active state on bottom tabs
                document.querySelectorAll('.bottom-tab-bar .tab-item').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                // Close sidebar if open
                document.querySelector('.sidebar')?.classList.remove('sidebar-open');
            });
        });

        // Mobile "+" Add button
        const btnAddMobile = document.getElementById('btn-add-mobile');
        if (btnAddMobile) {
            btnAddMobile.addEventListener('click', () => {
                generateModal.classList.remove('hidden');
            });
        }

        // Close any .modal-overlay by clicking its .close-modal button or backdrop
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('close-modal')) {
                e.target.closest('.modal-overlay').classList.add('hidden');
            }
            if (e.target.classList.contains('modal-overlay')) {
                e.target.classList.add('hidden');
            }
        });

        // API Docs button
        const btnApiDocs = document.createElement('button');
        btnApiDocs.className = 'btn-primary';
        btnApiDocs.id = 'btn-api-docs';
        btnApiDocs.textContent = 'API Docs';
        btnApiDocs.style.marginLeft = '1rem';
        btnApiDocs.addEventListener('click', () => {
            document.getElementById('modal-api-docs').classList.remove('hidden');
        });
        document.querySelector('.header-actions').appendChild(btnApiDocs);

        // Import Link Modal Bindings
        if (btnImportLink) {
            btnImportLink.addEventListener('click', () => {
                modalImportLink.classList.remove('hidden');
                importUrlInput.value = '';
                importStatus.style.display = 'none';
                btnDoImport.disabled = false;
                btnDoImport.textContent = 'Start Extraction';
            });
        }

        if (btnDoImport) {
            btnDoImport.addEventListener('click', handleImport);
        }
    }

    async function handleImport() {
        const url = importUrlInput.value.trim();
        if (!url) {
            showImportStatus('Please enter a valid URL', 'error');
            return;
        }

        btnDoImport.disabled = true;
        btnDoImport.textContent = 'Processing...';
        showImportStatus('Starting pipeline...', 'info');

        try {
            const response = await fetch('/webhook/openclaw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (response.ok) {
                showImportStatus(`Success! Video ID: ${data.video_id}. Processing started in background.`, 'success');
                setTimeout(() => {
                    modalImportLink.classList.add('hidden');
                    render(); // Refresh dashboard to show "Processing" if applicable
                }, 3000);
            } else {
                showImportStatus(`Error: ${data.detail || 'Failed to start pipeline'}`, 'error');
                btnDoImport.disabled = false;
                btnDoImport.textContent = 'Start Extraction';
            }
        } catch (error) {
            showImportStatus(`Network error: ${error.message}`, 'error');
            btnDoImport.disabled = false;
            btnDoImport.textContent = 'Start Extraction';
        }
    }

    function showImportStatus(message, type) {
        importStatus.textContent = message;
        importStatus.style.display = 'block';
        importStatus.style.background = type === 'error' ? 'rgba(255, 71, 87, 0.1)' :
            (type === 'success' ? 'rgba(46, 213, 115, 0.1)' : 'rgba(52, 152, 219, 0.1)');
        importStatus.style.color = type === 'error' ? '#ff4757' :
            (type === 'success' ? '#2ed573' : '#3498db');
        importStatus.style.border = `1px solid ${type === 'error' ? '#ff475755' : (type === 'success' ? '#2ed57355' : '#3498db55')}`;
    }

    // --- Video Detail Modal ---
    window.openVideoDetailModal = async function (videoId, autoPlay = false) {
        console.log(`[Interaction] Info icon click: opening modal for ${videoId}`);
        let modal = document.getElementById('modal-video-detail');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'modal-video-detail';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal" style="width: 90vw; max-width: 1200px; height: 90vh; overflow-x: hidden; overflow-y: auto;">
                    <div class="modal-header">
                        <h3 id="detail-title">Video Intelligence</h3>
                        <button class="close-modal">×</button>
                    </div>
                    <div class="detail-modal-body" id="detail-body">
                        <div style="flex: 1; text-align: center; color: var(--text-secondary); padding-top: 5rem;">Loading assets...</div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        modal.classList.remove('hidden');
        const bodyTag = document.getElementById('detail-body');
        bodyTag.innerHTML = '<div style="flex: 1; text-align: center; color: var(--text-secondary); padding-top: 5rem;">Retrieving deep intelligence...</div>';

        try {
            const response = await fetch(`/api/videos/${videoId}`);
            const data = await response.json();
            const displayTitle = humanize(data.topic || videoId);
            document.getElementById('detail-title').textContent = displayTitle;

            // 1. Top Section: Video Player + Script
            const videoUrl = data.video_url || '';
            const transcript = data.script_analysis?.transcript || 'No speech detected.';

            const topHTML = `
                <div class="detail-top-section">
                    ${videoUrl ? `
                    <div class="video-player-container">
                        <video id="detail-main-video" controls ${autoPlay ? 'autoplay' : ''}>
                            <source src="${videoUrl}" type="video/mp4">
                        </video>
                    </div>` : ''}
                    <div class="script-container">
                        ${data.script_analysis?.video_generation_prompt ? `
                        <div style="margin-bottom: 1.5rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <h4>AI Video Prompt</h4>
                                <button class="btn-secondary" style="font-size: 0.75rem; padding: 4px 8px;" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText); this.textContent='Copied!'; setTimeout(()=>this.textContent='Copy', 2000);">Copy</button>
                            </div>
                            <div class="script-box" style="background: var(--bg-primary); border-left: 3px solid var(--accent); font-family: monospace; font-size: 0.85rem;">${data.script_analysis.video_generation_prompt}</div>
                        </div>
                        ` : ''}
                        <h4>Oral Script / 文案</h4>
                        <div class="script-box">${transcript}</div>
                    </div>
                </div>
            `;

            // 2. Timeline Section: Keyframes ordered by time
            const keyframes = data.assets.keyframes || [];
            // Filename formats: time_00.00s.jpg OR frame_0001.jpg (legacy)
            const timeframes = keyframes.map((f, i) => {
                const match = f.url.match(/time_([\d\.]+)s/);
                let seconds = match ? parseFloat(match[1]) : i * 2.0; // Assume 0.5 fps for legacy
                return { ...f, seconds };
            }).sort((a, b) => a.seconds - b.seconds);

            const timelineHTML = `
                <div class="timeline-section">
                    <h4>Timeline View</h4>
                    <div class="timeline-grid">
                        ${timeframes.map(tk => `
                            <div class="timeline-item" onclick="document.getElementById('detail-main-video').currentTime = ${tk.seconds}">
                                <img src="${tk.url}">
                                <div class="timeline-time">${tk.seconds.toFixed(1)}s</div>
                                <a href="${tk.url}" download="frame_${tk.seconds.toFixed(0)}s.jpg" class="timeline-download" onclick="event.stopPropagation()">
                                    <i class="fas fa-download">↓</i>
                                </a>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;

            // 3. Relational Section: Actors, Clothes, Scenes
            const actors = data.assets.actors || [];
            const clothes = data.assets.clothes || [];
            const scenes = data.assets.scenes || [];

            const relationalHTML = `
                <div class="relational-section">
                    <div class="relational-col">
                        <h4>Products / 关联产品</h4>
                        <div class="relational-items">
                            ${clothes.map(c => `
                                <div class="relational-item" onclick="openEntityDetail('clothes', '${c.id}')" style="cursor:pointer; position:relative;">
                                    <button class="delete-entity-btn" onclick="event.stopPropagation(); deleteEntity('clothes', '${c.id}')" style="position:absolute; top:4px; right:4px; background:rgba(255,0,0,0.6); border:none; border-radius:4px; color:white; width:24px; height:24px; font-size:14px; cursor:pointer; display:flex; align-items:center; justify-content:center; z-index:10;" title="Delete Product">&times;</button>
                                    <img src="${c.url}">
                                    <div class="relational-item-info">
                                        <span>${c.display_name || humanize(c.id)}</span>
                                        <span>${c.gallery_urls ? c.gallery_urls.length + '张图' : '衣服'}</span>
                                    </div>
                                </div>
                            `).join('') || '<p style="font-size:0.8rem; color:var(--text-secondary)">None detected</p>'}
                        </div>
                    </div>

                    <div class="relational-col">
                        <h4>Location / 场景</h4>
                        <div class="relational-items">
                            ${scenes.map(s => `
                                <div class="relational-item" onclick="openEntityDetail('scenes', '${s.id}')" style="cursor:pointer; position:relative;">
                                    <button class="delete-entity-btn" onclick="event.stopPropagation(); deleteEntity('scenes', '${s.id}')" style="position:absolute; top:4px; right:4px; background:rgba(255,0,0,0.6); border:none; border-radius:4px; color:white; width:24px; height:24px; font-size:14px; cursor:pointer; display:flex; align-items:center; justify-content:center; z-index:10;" title="Delete Scene">&times;</button>
                                    <img src="${s.url}">
                                    <div class="relational-item-info">
                                        <span>${s.display_name || humanize(s.id)}</span>
                                        <span>场景</span>
                                    </div>
                                </div>
                            `).join('') || '<p style="font-size:0.8rem; color:var(--text-secondary)">None detected</p>'}
                        </div>
                    </div>
                </div>
            `;

            bodyTag.innerHTML = topHTML + timelineHTML + relationalHTML;

        } catch (e) {
            console.error("Video Detail fetch error:", e);
            bodyTag.innerHTML = `<div style="flex: 1; text-align: center; color: #ff6b6b; padding-top: 5rem;">Failed to load video details. Error context: ${e.message}</div>`;
        }
    }

    // Global delete entity function for the UI
    window.deleteEntity = async function (type, id) {
        if (!confirm(`Are you sure you want to delete this ${type.slice(0, -1)}?`)) return;
        try {
            const res = await fetch(`/api/entities/${type}/${id}`, { method: 'DELETE' });
            if (res.ok) {
                // Remove the closest item container
                const btn = event.target;
                const container = btn.closest('.relational-item') || btn.closest('.asset-card');
                if (container) container.remove();

                // If on a specific view, we might need a full refresh, but removing the element might be enough for the modal view.
            } else {
                const data = await res.json();
                alert(`Failed to delete: ${data.detail || 'Unknown error'}`);
            }
        } catch (e) {
            console.error("Delete error", e);
            alert("Delete failed: " + e.message);
        }
    };

    // ─── Global Image Lightbox ────────────────────────────────────────────────
    ; (function initLightbox() {
        // Create lightbox overlay element
        const lightbox = document.createElement('div');
        lightbox.id = 'image-lightbox';
        lightbox.className = 'lightbox-overlay hidden';
        lightbox.innerHTML = `
            <div class="lightbox-backdrop"></div>
            <img class="lightbox-img" src="" alt="Zoomed image">
            <button class="lightbox-close">×</button>
        `;
        document.body.appendChild(lightbox);

        const lbImg = lightbox.querySelector('.lightbox-img');
        const lbClose = lightbox.querySelector('.lightbox-close');
        const lbBackdrop = lightbox.querySelector('.lightbox-backdrop');

        // Close handlers
        lbClose.addEventListener('click', () => lightbox.classList.add('hidden'));
        lbBackdrop.addEventListener('click', () => lightbox.classList.add('hidden'));
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') lightbox.classList.add('hidden');
        });

        // Delegate: click any <img> to open lightbox
        document.body.addEventListener('click', (e) => {
            const img = e.target.closest('img');
            if (!img) return;
            // Skip images inside video players, nav logos, tiny icons (<32px)
            if (img.closest('video') || img.closest('.logo') || img.naturalWidth < 32) return;
            // Skip images inside specific interactive areas that already have their own click handler
            if (img.closest('.video-window') && !img.closest('.timeline-item') && !img.closest('.relational-item')) return;

            e.stopPropagation();
            lbImg.src = img.src;
            lightbox.classList.remove('hidden');
        });
    })();

    // --- Start Application ---
    init();
});
