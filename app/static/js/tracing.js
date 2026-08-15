let _ready = false;
let _tracer = null;
const _startTime = typeof performance !== "undefined" ? performance.now() : Date.now();

export function now() {
    return (typeof performance !== "undefined" ? performance.now() : Date.now()) - _startTime;
}

export async function setupTracing() {
    if (_ready || typeof window === "undefined") return;

    try {
        const otelApi = await import("@opentelemetry/api");
        const { WebTracerProvider } = await import("@opentelemetry/sdk-trace-web");
        const { Resource } = await import("@opentelemetry/resources");
        const { SemanticResourceAttributes } = await import("@opentelemetry/semantic-conventions");
        const { SimpleSpanProcessor, ConsoleSpanExporter } = await import("@opentelemetry/sdk-trace-base");
        const { XMLHttpRequestInstrumentation } = await import("@opentelemetry/instrumentation-xml-http-request");

        const provider = new WebTracerProvider({
            resource: new Resource({
                [SemanticResourceAttributes.SERVICE_NAME]: "comfy-meta-viewer-web",
            }),
        });
        provider.addSpanProcessor(new SimpleSpanProcessor(new ConsoleSpanExporter()));

        provider.register();

        try {
            const xhrInst = new XMLHttpRequestInstrumentation({
                ignoreUrls: [/esm\.sh/],
            });
            xhrInst.setTracerProvider(provider);
            xhrInst.enable();
        } catch (e) {
            console.warn("[tracing] xhr instrumentation failed", e);
        }

        _tracer = otelApi.trace.getTracer("comfy-meta-viewer-web");
        _ready = true;
        console.info("[tracing] opentelemetry web tracing enabled -> console");
    } catch (e) {
        console.warn("[tracing] setup failed (cdn/importmap issue)", e);
        _tracer = _noopTracer();
        _ready = true;
    }
}

function _noopTracer() {
    return {
        startSpan(name) {
            return _noopSpan(name);
        },
        startActiveSpan(name, fn) {
            return fn(_noopSpan(name));
        },
    };
}

function _noopSpan(name) {
    const ts = now();
    return {
        setAttribute() {},
        setAttributes() {},
        addEvent() {},
        end() {},
        spanContext() {
            return { traceId: "noop", spanId: "noop", traceFlags: 0 };
        },
        _name: name,
        _ts: ts,
    };
}

export function getTracer() {
    if (!_tracer) {
        _tracer = _noopTracer();
    }
    return _tracer;
}

export function traceSpan(name, attrs = {}) {
    const t = getTracer();
    return t.startSpan(name, { attributes: attrs });
}

export async function traceAsync(name, attrs = {}, fn) {
    const t = getTracer();
    const span = t.startSpan(name, { attributes: attrs });
    try {
        const result = await fn(span);
        span.end();
        return result;
    } catch (err) {
        span.setAttribute("error", true);
        span.setAttribute("error.message", err?.message || String(err));
        span.end();
        throw err;
    }
}
