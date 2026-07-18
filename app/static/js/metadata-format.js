function isLoraKey(key) {
    return ['lora', 'loras'].includes(String(key).trim().toLowerCase());
}

function isLoraAdapter(value) {
    return value !== null
        && typeof value === 'object'
        && !Array.isArray(value)
        && typeof value.name === 'string'
        && value.name.trim().length > 0;
}

function formatLoraStrength(adapter) {
    const hasModelStrength = adapter.strength_model !== null
        && adapter.strength_model !== undefined;
    const hasClipStrength = adapter.strength_clip !== null
        && adapter.strength_clip !== undefined;

    if (hasModelStrength && hasClipStrength) {
        if (adapter.strength_model === adapter.strength_clip) {
            return `strength: ${adapter.strength_model}`;
        }
        return `model: ${adapter.strength_model}, clip: ${adapter.strength_clip}`;
    }
    if (hasModelStrength) return `model: ${adapter.strength_model}`;
    if (hasClipStrength) return `clip: ${adapter.strength_clip}`;
    if (adapter.strength !== null && adapter.strength !== undefined) {
        return `strength: ${adapter.strength}`;
    }
    return '';
}

function formatLoraAdapter(adapter) {
    const strength = formatLoraStrength(adapter);
    return strength ? `${adapter.name} (${strength})` : adapter.name;
}

export function getStringValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
}

export function getMetadataStringValue(key, value) {
    if (
        isLoraKey(key)
        && Array.isArray(value)
        && value.length > 0
        && value.every(isLoraAdapter)
    ) {
        return value.map(formatLoraAdapter).join('\n');
    }
    return getStringValue(value);
}
