import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "DustinMarblePano360Viewer";
const VIEWER_MIN_HEIGHT = 360;
const MSG_SOURCE = "dustin.marble.pano";
const PANO_UI_KEY = "dustin_pano_360";

/** Same directory as this module (ComfyUI serves WEB_DIRECTORY without a /js/ URL prefix). */
function getEmbedPageUrl() {
    return new URL("pano_embed.html", import.meta.url).href;
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
    const iframe = document.createElement("iframe");
    iframe.className = "dustin-marble-pano-iframe";
    iframe.title = "360° panorama viewer";
    iframe.setAttribute("sandbox", "allow-scripts allow-same-origin");
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "0";
    iframe.style.display = "block";
    iframe.style.background = "#111";
    iframe.src = getEmbedPageUrl();

    container.appendChild(iframe);

    let embedReady = false;
    let pendingUrl = null;

    function postToEmbed(message) {
        if (!iframe.contentWindow) {
            return;
        }
        iframe.contentWindow.postMessage({ source: MSG_SOURCE, ...message }, "*");
    }

    function sendLoad(url) {
        if (!url) {
            return;
        }
        if (!embedReady) {
            pendingUrl = url;
            return;
        }
        postToEmbed({ type: "load", url });
    }

    function onMessage(event) {
        if (event.source !== iframe.contentWindow) {
            return;
        }
        const data = event.data;
        if (!data || data.source !== MSG_SOURCE) {
            return;
        }
        if (data.type === "ready") {
            embedReady = true;
            if (pendingUrl) {
                sendLoad(pendingUrl);
                pendingUrl = null;
            }
        }
    }

    window.addEventListener("message", onMessage);

    function loadFromImages(images) {
        if (!images?.length) {
            return;
        }
        sendLoad(imageToViewUrl(images[0]));
    }

    function resize() {
        postToEmbed({ type: "resize" });
    }

    function destroy() {
        window.removeEventListener("message", onMessage);
        iframe.remove();
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
            container.style.height = "100%";
            container.style.minHeight = `${VIEWER_MIN_HEIGHT}px`;
            container.style.position = "relative";
            container.style.overflow = "hidden";
            container.style.boxSizing = "border-box";
            container.dataset.captureWheel = "true";

            const pano = createPanoViewer(this, container);
            this.panoController = pano;

            const syncViewerLayout = () => {
                requestAnimationFrame(() => pano.resize());
            };

            this.panoWidget = this.addDOMWidget("pano_360_viewer", "div", container, {
                getMinHeight: () => VIEWER_MIN_HEIGHT,
                getHeight: () => VIEWER_MIN_HEIGHT,
                hideOnZoom: false,
                margin: 0,
                afterResize: syncViewerLayout,
            });

            const origOnResize = this.onResize;
            this.onResize = function () {
                origOnResize?.apply(this, arguments);
                syncViewerLayout();
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
            const panoImages = message?.[PANO_UI_KEY] ?? message?.images;
            this.panoController?.loadFromImages(panoImages);
            requestAnimationFrame(() => this.panoController?.resize());
        };
    },
});
