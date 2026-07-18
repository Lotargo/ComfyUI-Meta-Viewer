import test from 'node:test';
import assert from 'node:assert/strict';

import {
    getMetadataStringValue,
    getStringValue,
} from '../app/static/js/metadata-format.js';

test('LoRA adapters are formatted as readable metadata', () => {
    const value = [
        { name: 'equal.safetensors', strength_model: 1, strength_clip: 1 },
        { name: 'split.safetensors', strength_model: 0.8, strength_clip: 0.6 },
        { name: 'legacy.safetensors', strength: 1.25 },
    ];

    assert.equal(
        getMetadataStringValue('loras', value),
        [
            'equal.safetensors (strength: 1)',
            'split.safetensors (model: 0.8, clip: 0.6)',
            'legacy.safetensors (strength: 1.25)',
        ].join('\n'),
    );
});

test('non-LoRA objects retain JSON formatting', () => {
    const value = [{ name: 'adapter.safetensors', strength: 1 }];

    assert.equal(getMetadataStringValue('other', value), getStringValue(value));
    assert.match(getStringValue(value), /^\[/);
});
