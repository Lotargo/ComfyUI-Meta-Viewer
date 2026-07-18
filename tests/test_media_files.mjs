import assert from 'node:assert/strict';
import test from 'node:test';

import {
    SUPPORTED_MEDIA_EXTENSIONS,
    isSupportedMediaFile,
} from '../app/static/js/media-files.js';

test('upload media filter accepts supported images and videos', () => {
    assert.equal(isSupportedMediaFile({ name: 'still.PNG' }), true);
    assert.equal(isSupportedMediaFile({ name: 'clip.MP4' }), true);
    assert.equal(isSupportedMediaFile({ name: 'animation.webm' }), true);
    assert.equal(isSupportedMediaFile({ name: 'notes.txt' }), false);
    assert.ok(SUPPORTED_MEDIA_EXTENSIONS.includes('.mkv'));
});
