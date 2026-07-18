import {
    sortKey,
    sortDir,
    sidebarSortKey,
    sidebarSortDir,
    setSortKey,
    setSortDir,
    setSidebarSortKey,
    setSidebarSortDir,
    foldersSortKey,
    foldersSortDir,
    setFoldersSortKey,
    setFoldersSortDir,
    albumsSortKey,
    albumsSortDir,
    setAlbumsSortKey,
    setAlbumsSortDir,
    currentCollection,
    dom,
    saveState,
} from '../state.js';
import {
    loadCollectionImages,
    loadSidebarImages,
    invalidateApiCache,
} from '../api.js';


const sortOptions = [
    { key: 'name', label: 'Name' },
    { key: 'date', label: 'Date' },
    { key: 'size', label: 'Size' },
    { key: 'type', label: 'Type' }
];

const folderSortOptions = [
    { key: 'name', label: 'Name' },
    { key: 'scanned_at', label: 'Date Scanned' },
    { key: 'image_count', label: 'Image Count' }
];

const albumSortOptions = [
    { key: 'name', label: 'Name' },
    { key: 'updated_at', label: 'Last Updated' },
    { key: 'asset_count', label: 'Image Count' }
];

const dirOptions = [
    { dir: 'asc', label: 'Ascending' },
    { dir: 'desc', label: 'Descending' }
];

function closeRatingFilterMenu() {
    if (dom.ratingFilterMenu) dom.ratingFilterMenu.style.display = 'none';
    dom.ratingFilterBtn?.setAttribute('aria-expanded', 'false');
}

function renderSortMenu(menuElement, currentKey, currentDir, options, onSortSelect, onDirSelect) {
    menuElement.innerHTML = '';
    
    options.forEach(opt => {
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
        const foldersMenu = document.querySelector('#folders-sort-dropdown-menu');
        if (foldersMenu) foldersMenu.style.display = 'none';
        const albumsMenu = document.querySelector('#viewer-albums-sort-dropdown-menu');
        if (albumsMenu) albumsMenu.style.display = 'none';
        closeRatingFilterMenu();
        
        if (isVisible) {
            sortMenu.style.display = 'none';
            sortBtn.setAttribute('aria-expanded', 'false');
        } else {
            renderSortMenu(sortMenu, sortKey, sortDir, sortOptions,
                async (newKey) => {
                    setSortKey(newKey);
                    saveState();
                    sortMenu.style.display = 'none';
                    sortBtn.setAttribute('aria-expanded', 'false');
                    invalidateApiCache();
                    if (currentCollection.id) {
                        await loadCollectionImages({ ...currentCollection }, { force: true });
                    }
                }, 
                async (newDir) => {
                    setSortDir(newDir);
                    saveState();
                    sortMenu.style.display = 'none';
                    sortBtn.setAttribute('aria-expanded', 'false');
                    invalidateApiCache();
                    if (currentCollection.id) {
                        await loadCollectionImages({ ...currentCollection }, { force: true });
                    }
                }
            );
            sortMenu.style.display = 'flex';
            sortBtn.setAttribute('aria-expanded', 'true');
        }
    };
}

export function bindSidebarSortEvents() {
    const sidebarSortBtn = document.querySelector('#sidebar-sort-btn');
    const sidebarSortMenu = document.querySelector('#sidebar-sort-dropdown-menu');
    if (!sidebarSortBtn || !sidebarSortMenu) return;
    
    sidebarSortBtn.onclick = (e) => {
        e.stopPropagation();
        closeRatingFilterMenu();
        const isVisible = sidebarSortMenu.style.display !== 'none';
        
        const sortMenu = document.querySelector('#sort-dropdown-menu');
        if (sortMenu) sortMenu.style.display = 'none';
        document.querySelector('#sort-btn')?.setAttribute('aria-expanded', 'false');
        const foldersMenu = document.querySelector('#folders-sort-dropdown-menu');
        if (foldersMenu) foldersMenu.style.display = 'none';
        const albumsMenu = document.querySelector('#viewer-albums-sort-dropdown-menu');
        if (albumsMenu) albumsMenu.style.display = 'none';
        
        if (isVisible) {
            sidebarSortMenu.style.display = 'none';
        } else {
            renderSortMenu(sidebarSortMenu, sidebarSortKey, sidebarSortDir, sortOptions,
                async (newKey) => {
                    setSidebarSortKey(newKey);
                    saveState();
                    sidebarSortMenu.style.display = 'none';
                    invalidateApiCache();
                    await loadSidebarImages({ force: true });
                },
                async (newDir) => {
                    setSidebarSortDir(newDir);
                    saveState();
                    sidebarSortMenu.style.display = 'none';
                    invalidateApiCache();
                    await loadSidebarImages({ force: true });
                }
            );
            sidebarSortMenu.style.display = 'flex';
        }
    };
}

export function bindFoldersSortEvents() {
    const foldersSortBtn = document.querySelector('#folders-sort-btn');
    const foldersSortMenu = document.querySelector('#folders-sort-dropdown-menu');
    if (!foldersSortBtn || !foldersSortMenu) return;
    
    foldersSortBtn.onclick = (e) => {
        e.stopPropagation();
        closeRatingFilterMenu();
        const isVisible = foldersSortMenu.style.display !== 'none';
        
        const sortMenu = document.querySelector('#sort-dropdown-menu');
        if (sortMenu) sortMenu.style.display = 'none';
        document.querySelector('#sort-btn')?.setAttribute('aria-expanded', 'false');
        const sidebarMenu = document.querySelector('#sidebar-sort-dropdown-menu');
        if (sidebarMenu) sidebarMenu.style.display = 'none';
        const albumsMenu = document.querySelector('#viewer-albums-sort-dropdown-menu');
        if (albumsMenu) albumsMenu.style.display = 'none';
        
        if (isVisible) {
            foldersSortMenu.style.display = 'none';
        } else {
            renderSortMenu(foldersSortMenu, foldersSortKey, foldersSortDir, folderSortOptions,
                async (newKey) => {
                    setFoldersSortKey(newKey);
                    saveState();
                    foldersSortMenu.style.display = 'none';
                    const { renderFoldersList } = await import('./sidebar.js');
                    await renderFoldersList();
                },
                async (newDir) => {
                    setFoldersSortDir(newDir);
                    saveState();
                    foldersSortMenu.style.display = 'none';
                    const { renderFoldersList } = await import('./sidebar.js');
                    await renderFoldersList();
                }
            );
            foldersSortMenu.style.display = 'flex';
        }
    };
}

export function bindAlbumsSortEvents() {
    const albumsSortBtn = dom.albumsSortBtn;
    const albumsSortMenu = dom.albumsSortDropdown;
    if (!albumsSortBtn || !albumsSortMenu) return;

    albumsSortBtn.onclick = event => {
        event.stopPropagation();
        closeRatingFilterMenu();
        const isVisible = albumsSortMenu.style.display !== 'none';
        document.querySelectorAll('#sort-dropdown-menu, #sidebar-sort-dropdown-menu, #folders-sort-dropdown-menu')
            .forEach(menu => { menu.style.display = 'none'; });
        document.querySelector('#sort-btn')?.setAttribute('aria-expanded', 'false');

        if (isVisible) {
            albumsSortMenu.style.display = 'none';
            return;
        }

        renderSortMenu(albumsSortMenu, albumsSortKey, albumsSortDir, albumSortOptions,
            async newKey => {
                setAlbumsSortKey(newKey);
                saveState();
                albumsSortMenu.style.display = 'none';
                const { renderAlbumsList } = await import('./sidebar.js');
                await renderAlbumsList();
            },
            async newDir => {
                setAlbumsSortDir(newDir);
                saveState();
                albumsSortMenu.style.display = 'none';
                const { renderAlbumsList } = await import('./sidebar.js');
                await renderAlbumsList();
            }
        );
        albumsSortMenu.style.display = 'flex';
    };
}

export function initSorting() {
    bindSidebarSortEvents();
    bindCentralSortEvents();
    bindFoldersSortEvents();
    bindAlbumsSortEvents();
    
    document.addEventListener('click', () => {
        const sortMenu = document.querySelector('#sort-dropdown-menu');
        if (sortMenu) sortMenu.style.display = 'none';
        document.querySelector('#sort-btn')?.setAttribute('aria-expanded', 'false');
        const sidebarMenu = document.querySelector('#sidebar-sort-dropdown-menu');
        if (sidebarMenu) sidebarMenu.style.display = 'none';
        const foldersMenu = document.querySelector('#folders-sort-dropdown-menu');
        if (foldersMenu) foldersMenu.style.display = 'none';
        const albumsMenu = document.querySelector('#viewer-albums-sort-dropdown-menu');
        if (albumsMenu) albumsMenu.style.display = 'none';
    });
}
