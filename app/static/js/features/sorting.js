import {
    sortKey,
    sortDir,
    sidebarSortKey,
    sidebarSortDir,
    setSortKey,
    setSortDir,
    setSidebarSortKey,
    setSidebarSortDir,
    currentFolderId,
    dom,
} from '../state.js';
import {
    loadFolderImages,
    loadSidebarImages,
    invalidateApiCache,
} from '../api.js';


const sortOptions = [
    { key: 'name', label: 'Name' },
    { key: 'date', label: 'Date' },
    { key: 'size', label: 'Size' },
    { key: 'type', label: 'Type' }
];

const dirOptions = [
    { dir: 'asc', label: 'Ascending' },
    { dir: 'desc', label: 'Descending' }
];

function renderSortMenu(menuElement, currentKey, currentDir, onSortSelect, onDirSelect) {
    menuElement.innerHTML = '';
    
    sortOptions.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'dropdown-item';
        const activeIndicator = opt.key === currentKey ? '•' : '';
        btn.innerHTML = `<span class="indicator">${activeIndicator}</span><span class="label">${opt.label}</span>`;
        btn.onclick = (e) => {
            e.stopPropagation();
            onSortSelect(opt.key);
        };
        menuElement.appendChild(btn);
    });
    
    const divider = document.createElement('div');
    divider.className = 'dropdown-divider';
    menuElement.appendChild(divider);
    
    dirOptions.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'dropdown-item';
        const activeIndicator = opt.dir === currentDir ? '•' : '';
        btn.innerHTML = `<span class="indicator">${activeIndicator}</span><span class="label">${opt.label}</span>`;
        btn.onclick = (e) => {
            e.stopPropagation();
            onDirSelect(opt.dir);
        };
        menuElement.appendChild(btn);
    });
}

export function bindCentralSortEvents() {
    const sortBtn = document.querySelector('#sort-btn');
    const sortMenu = document.querySelector('#sort-dropdown-menu');
    if (!sortBtn || !sortMenu) return;
    
    sortBtn.onclick = (e) => {
        e.stopPropagation();
        const isVisible = sortMenu.style.display !== 'none';
        
        const sidebarMenu = document.querySelector('#sidebar-sort-dropdown-menu');
        if (sidebarMenu) sidebarMenu.style.display = 'none';
        
        if (isVisible) {
            sortMenu.style.display = 'none';
        } else {
            renderSortMenu(sortMenu, sortKey, sortDir, 
                async (newKey) => {
                    setSortKey(newKey);
                    sortMenu.style.display = 'none';
                    invalidateApiCache();
                    const folderName = dom.folderNameEl ? dom.folderNameEl.textContent : '';
                    if (currentFolderId) {
                        await loadFolderImages(currentFolderId, folderName, { force: true });
                    }
                }, 
                async (newDir) => {
                    setSortDir(newDir);
                    sortMenu.style.display = 'none';
                    invalidateApiCache();
                    const folderName = dom.folderNameEl ? dom.folderNameEl.textContent : '';
                    if (currentFolderId) {
                        await loadFolderImages(currentFolderId, folderName, { force: true });
                    }
                }
            );
            sortMenu.style.display = 'flex';
        }
    };
}

export function bindSidebarSortEvents() {
    const sidebarSortBtn = document.querySelector('#sidebar-sort-btn');
    const sidebarSortMenu = document.querySelector('#sidebar-sort-dropdown-menu');
    if (!sidebarSortBtn || !sidebarSortMenu) return;
    
    sidebarSortBtn.onclick = (e) => {
        e.stopPropagation();
        const isVisible = sidebarSortMenu.style.display !== 'none';
        
        const sortMenu = document.querySelector('#sort-dropdown-menu');
        if (sortMenu) sortMenu.style.display = 'none';
        
        if (isVisible) {
            sidebarSortMenu.style.display = 'none';
        } else {
            renderSortMenu(sidebarSortMenu, sidebarSortKey, sidebarSortDir,
                async (newKey) => {
                    setSidebarSortKey(newKey);
                    sidebarSortMenu.style.display = 'none';
                    invalidateApiCache();
                    await loadSidebarImages({ force: true });
                },
                async (newDir) => {
                    setSidebarSortDir(newDir);
                    sidebarSortMenu.style.display = 'none';
                    invalidateApiCache();
                    await loadSidebarImages({ force: true });
                }
            );
            sidebarSortMenu.style.display = 'flex';
        }
    };
}

export function initSorting() {
    bindSidebarSortEvents();
    
    document.addEventListener('click', () => {
        const sortMenu = document.querySelector('#sort-dropdown-menu');
        if (sortMenu) sortMenu.style.display = 'none';
        const sidebarMenu = document.querySelector('#sidebar-sort-dropdown-menu');
        if (sidebarMenu) sidebarMenu.style.display = 'none';
    });
}
