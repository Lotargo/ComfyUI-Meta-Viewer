/**
 * Skeleton loading components
 */

export function skeletonImageItem() {
    return `
        <div class="skeleton-image-item">
            <div class="skeleton skeleton-thumb"></div>
            <div class="skeleton-info">
                <div class="skeleton skeleton-text" style="width: 80%"></div>
                <div class="skeleton skeleton-text-sm" style="width: 50%"></div>
            </div>
        </div>
    `;
}

export function skeletonGalleryCard() {
    return `
        <div class="skeleton-gallery-card">
            <div class="skeleton skeleton-img"></div>
            <div class="skeleton-content">
                <div class="skeleton skeleton-text" style="width: 70%"></div>
                <div class="skeleton skeleton-text-sm" style="width: 40%"></div>
            </div>
        </div>
    `;
}

export function skeletonMetaView() {
    return `
        <div class="skeleton-meta-view">
            <div class="skeleton-meta-header">
                <div class="skeleton skeleton-thumb-lg"></div>
                <div class="skeleton-info">
                    <div class="skeleton skeleton-text-lg" style="width: 60%"></div>
                    <div class="skeleton skeleton-text-sm" style="width: 40%"></div>
                </div>
            </div>
            ${skeletonCategory()}
            ${skeletonCategory()}
            ${skeletonCategory()}
        </div>
    `;
}

export function skeletonCategory() {
    return `
        <div class="skeleton-category">
            <div class="skeleton-category-header">
                <div class="skeleton skeleton-text" style="width: 20px; height: 20px; border-radius: 50%"></div>
                <div class="skeleton skeleton-text" style="width: 120px"></div>
            </div>
            <div class="skeleton-category-body">
                ${skeletonRow()}
                ${skeletonRow()}
                ${skeletonRow()}
            </div>
        </div>
    `;
}

export function skeletonRow() {
    return `
        <div class="skeleton-row">
            <div class="skeleton skeleton-key skeleton-text-sm"></div>
            <div class="skeleton skeleton-value skeleton-text" style="flex: 1"></div>
        </div>
    `;
}

export function skeletonLightbox() {
    return `
        <div class="skeleton-meta-view">
            ${skeletonCategory()}
            ${skeletonCategory()}
        </div>
    `;
}
