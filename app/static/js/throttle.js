/**
 * Leading + trailing throttle for expensive operations (image loads,
 * preview swaps) driven by high-frequency events such as held-down
 * navigation keys.
 *
 * - The first call in a quiet period runs immediately (no added latency
 *   for single presses).
 * - Calls arriving inside the window collapse into ONE trailing call with
 *   the LATEST arguments, so rapid navigation always settles on the
 *   current item instead of starving behind cancelled work.
 *
 * Pure logic over Date.now/setTimeout: fully unit-testable in Node.
 */
export function createTrailingThrottle(fn, windowMs) {
    let lastFire = 0;
    let timer = null;
    let pendingArgs = null;

    function fire() {
        timer = null;
        lastFire = Date.now();
        const args = pendingArgs;
        pendingArgs = null;
        fn(...args);
    }

    function schedule(...args) {
        pendingArgs = args;
        if (timer) return;
        const elapsed = Date.now() - lastFire;
        if (elapsed >= windowMs) {
            fire();
        } else {
            timer = setTimeout(fire, windowMs - elapsed);
        }
    }

    schedule.cancel = () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
        pendingArgs = null;
    };

    return schedule;
}
