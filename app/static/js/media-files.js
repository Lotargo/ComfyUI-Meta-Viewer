export const SUPPORTED_MEDIA_EXTENSIONS = Object.freeze([
    '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff',
    '.mp4', '.m4v', '.mov', '.webm', '.mkv', '.avi',
]);

export function isSupportedMediaFile(file) {
    const name = String(file?.name || '').toLowerCase();
    return SUPPORTED_MEDIA_EXTENSIONS.some(extension => name.endsWith(extension));
}
