import test from 'node:test';
import assert from 'node:assert/strict';

import { createTrailingThrottle } from '../app/static/js/throttle.js';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

test('first call runs immediately with no added latency', () => {
    const seen = [];
    const throttled = createTrailingThrottle((...args) => seen.push(args), 1000);
    throttled('a');
    assert.deepEqual(seen, [['a']]);
    throttled.cancel();
});

test('rapid calls collapse into one trailing call with the latest args', async () => {
    const seen = [];
    const throttled = createTrailingThrottle((...args) => seen.push(args), 40);
    throttled('first');
    assert.deepEqual(seen, [['first']]);
    throttled('second');
    throttled('third');
    throttled('fourth');
    await sleep(80);
    assert.deepEqual(seen, [['first'], ['fourth']]);
});

test('calls spaced beyond the window each run immediately', async () => {
    const seen = [];
    const throttled = createTrailingThrottle((...args) => seen.push(args), 30);
    throttled('a');
    await sleep(60);
    throttled('b');
    await sleep(60);
    throttled('c');
    assert.deepEqual(seen, [['a'], ['b'], ['c']]);
});

test('cancel drops the pending trailing call', async () => {
    const seen = [];
    const throttled = createTrailingThrottle((...args) => seen.push(args), 30);
    throttled('a');
    throttled('b');
    throttled.cancel();
    await sleep(60);
    assert.deepEqual(seen, [['a']]);
});
