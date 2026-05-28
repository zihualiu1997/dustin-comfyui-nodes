import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "DustinMarblePano360Viewer";
const VIEWER_MIN_HEIGHT = 360;

let pannellumLoadPromise = null;

/** Keep LiteGraph / ComfyUI canvas from treating drags inside the viewer as node moves. */
function preventNodePointerCapture(element) {
    const stop = (event) => {
        event.stopPropagation();
    };
    const types = [
        "mousedown",
        "mousemove",
        "mouseup",
        "pointerdown",
        "pointermove",
        "pointerup",
        "wheel",
        "touchstart",
        "touchmove",
        "touchend",
        "contextmenu",
    ];
    for (const type of types) {
        element.addEventListener(type, stop, false);
    }
}

function getPannellumBaseUrl() {
    const scripts = [...document.querySelectorAll("script[src]")];
    const selfScript = scripts.find((entry) => entry.src.includes("marble_pano_viewer.js"));
    if (selfScript) {
        return selfScript.src.replace(/marble_pano_viewer\.js(?:\?.*)?$/, "vendor/pannellum/");
    }
    return "/extensions/dustin-comfyui-nodes/vendor/pannellum/";
}

function loadStylesheet(href) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`link[href="${href}"]`)) {
            resolve();
            return;
        }
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.onload = () => resolve();
        link.onerror = () => reject(new Error(`Failed to load stylesheet: ${href}`));
        document.head.appendChild(link);
    });
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (window.pannellum) {
            resolve(window.pannellum);
            return;
        }
        const existing = document.querySelector(`script[src="${src}"]`);
        if (existing) {
            existing.addEventListener("load", () => resolve(window.pannellum));
            existing.addEventListener("error", reject);
            return;
        }
        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.onload = () => resolve(window.pannellum);
        script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
        document.head.appendChild(script);
    });
}

function ensurePannellum() {
    if (window.pannellum) {
        return Promise.resolve(window.pannellum);
    }
    if (!pannellumLoadPromise) {
        const base = getPannellumBaseUrl();
        pannellumLoadPromise = loadStylesheet(`${base}pannellum.css`)
            .then(() => loadScript(`${base}pannellum.js`))
            .then(() => window.pannellum);
    }
    return pannellumLoadPromise;
}

function imageToViewUrl(image) {
    const params = new URLSearchParams();
    params.set("filename", image.filename);
    params.set("type", image.type || "temp");
    if (image.subfolder) {
        params.set("subfolder", image.subfolder);
    }
    params.set("rand", String(Math.random()));
    return api.apiURL(`/view?${params.toString()}`);
}

function scheduleViewerResize(viewer) {
    if (!viewer || typeof viewer.resize !== "function") {
        return;
    }
    requestAnimationFrame(() => {
        viewer.resize();
        requestAnimationFrame(() => viewer.resize());
    });
}

function createPanoViewer(node, container) {
    const mount = document.createElement("div");
    mount.className = "dustin-marble-pano-mount";
    mount.style.width = "100%";
    mount.style.height = `${VIEWER_MIN_HEIGHT}px`;
    mount.style.minHeight = `${VIEWER_MIN_HEIGHT}px`;
    mount.style.borderRadius = "6px";
    mount.style.overflow = "hidden";
    mount.style.background = "#111";
    mount.style.touchAction = "none";
    container.appendChild(mount);
    preventNodePointerCapture(container);
    preventNodePointerCapture(mount);

    const placeholder = document.createElement("div");
    placeholder.textContent = "Queue the workflow to load a 360° panorama.";
    placeholder.style.color = "#aaa";
    placeholder.style.fontSize = "12px";
    placeholder.style.padding = "12px";
    placeholder.style.textAlign = "center";
    mount.appendChild(placeholder);

    let viewer = null;
    let resizeObserver = null;

    function bindViewerResize() {
        if (!viewer) {
            return;
        }
        scheduleViewerResize(viewer);
        if (typeof viewer.on === "function") {
            viewer.on("load", () => scheduleViewerResize(viewer));
            viewer.on("scenechange", () => scheduleViewerResize(viewer));
        }
    }

    function teardownViewer() {
        resizeObserver?.disconnect();
        resizeObserver = null;
        if (viewer) {
            viewer.destroy();
            viewer = null;
        }
        node.panoViewer = null;
    }

    async function loadFromImages(images) {
        if (!images?.length) {
            return;
        }
        const pannellumLib = await ensurePannellum();
        const panoramaUrl = imageToViewUrl(images[0]);

        teardownViewer();
        mount.innerHTML = "";

        viewer = pannellumLib.viewer(mount, {
            type: "equirectangular",
            panorama: panoramaUrl,
            autoLoad: true,
            showControls: true,
            mouseZoom: true,
            draggable: true,
            friction: 0.15,
            hfov: 100,
            minHfov: 40,
            maxHfov: 120,
        });
        node.panoViewer = viewer;

        const pnlmRoot = mount.querySelector(".pnlm-container");
        if (pnlmRoot) {
            preventNodePointerCapture(pnlmRoot);
        }

        bindViewerResize();

        if (typeof ResizeObserver !== "undefined") {
            resizeObserver = new ResizeObserver(() => scheduleViewerResize(viewer));
            resizeObserver.observe(mount);
            resizeObserver.observe(container);
        }
    }

    function resize() {
        scheduleViewerResize(viewer);
    }

    function destroy() {
        teardownViewer();
    }

    return { loadFromImages, resize, destroy };
}

app.registerExtension({
    name: "dustin.marble.pano360viewer",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const container = document.createElement("div");
            container.className = "dustin-marble-pano-container";
            container.style.width = "100%";
            container.style.height = `${VIEWER_MIN_HEIGHT}px`;
            container.style.minHeight = `${VIEWER_MIN_HEIGHT}px`;
            container.style.position = "relative";
            container.style.overflow = "hidden";
            container.dataset.captureWheel = "true";

            const pano = createPanoViewer(this, container);
            this.panoController = pano;

            this.panoWidget = this.addDOMWidget("pano_360_viewer", "div", container, {
                getMinHeight: () => VIEWER_MIN_HEIGHT,
                hideOnZoom: false,
            });

            const resizeViewer = () => {
                const widgetHeight = this.panoWidget?.computedHeight;
                const height =
                    typeof widgetHeight === "number" && widgetHeight > 0
                        ? widgetHeight
                        : VIEWER_MIN_HEIGHT;
                container.style.height = `${height}px`;
                const mount = container.querySelector(".dustin-marble-pano-mount");
                if (mount) {
                    mount.style.height = `${height}px`;
                }
                pano.resize();
            };
            this.panoWidget.onResize = resizeViewer;
            const origOnResize = this.onResize;
            this.onResize = function () {
                origOnResize?.apply(this, arguments);
                resizeViewer();
            };

            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                pano.destroy();
                origOnRemoved?.apply(this, arguments);
            };

            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            this.panoController?.loadFromImages(message?.images);
            requestAnimationFrame(() => this.panoController?.resize());
        };
    },
});
