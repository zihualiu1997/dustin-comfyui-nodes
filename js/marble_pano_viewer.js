import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "DustinMarblePano360Viewer";
const VIEWER_MIN_HEIGHT = 360;

let pannellumLoadPromise = null;

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

function createPanoViewer(node, container) {
    const mount = document.createElement("div");
    mount.className = "dustin-marble-pano-mount";
    mount.style.width = "100%";
    mount.style.height = "100%";
    mount.style.minHeight = `${VIEWER_MIN_HEIGHT}px`;
    mount.style.borderRadius = "6px";
    mount.style.overflow = "hidden";
    mount.style.background = "#111";
    container.appendChild(mount);

    const placeholder = document.createElement("div");
    placeholder.textContent = "Queue the workflow to load a 360° panorama.";
    placeholder.style.color = "#aaa";
    placeholder.style.fontSize = "12px";
    placeholder.style.padding = "12px";
    placeholder.style.textAlign = "center";
    mount.appendChild(placeholder);

    let viewer = null;

    async function loadFromImages(images) {
        if (!images?.length) {
            return;
        }
        const pannellumLib = await ensurePannellum();
        const panoramaUrl = imageToViewUrl(images[0]);

        if (viewer) {
            viewer.destroy();
            viewer = null;
        }
        mount.innerHTML = "";

        viewer = pannellumLib.viewer(mount, {
            type: "equirectangular",
            panorama: panoramaUrl,
            autoLoad: true,
            showControls: true,
            mouseZoom: true,
            draggable: true,
            hfov: 100,
            minHfov: 40,
            maxHfov: 120,
        });
        node.panoViewer = viewer;
    }

    function resize() {
        if (viewer && typeof viewer.resize === "function") {
            viewer.resize();
        }
    }

    return { loadFromImages, resize };
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
            container.style.position = "relative";

            const pano = createPanoViewer(this, container);
            this.panoController = pano;

            this.panoWidget = this.addDOMWidget("pano_360_viewer", "div", container, {
                getMinHeight: () => VIEWER_MIN_HEIGHT,
                hideOnZoom: false,
            });

            const resizeViewer = () => {
                requestAnimationFrame(() => pano.resize());
            };
            this.panoWidget.onResize = resizeViewer;
            const origOnResize = this.onResize;
            this.onResize = function () {
                origOnResize?.apply(this, arguments);
                resizeViewer();
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
