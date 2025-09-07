// MIT License — NanoBanana Try-On frontend (plain JS version)

const template = document.createElement("template");
template.innerHTML = `
  <style>@import url('./styles.css');</style>
  <button class="tryon-btn" part="button" aria-haspopup="dialog"></button>
`;

class TryOnButton extends HTMLElement {
  static get observedAttributes() { return ["garment-url", "api-endpoint", "text"]; }
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.append(template.content.cloneNode(true));
    this.apiEndpoint = "/api/tryon";
    this.text = "Try on";
  }
  connectedCallback() {
    this._refresh();
    this.shadowRoot.querySelector("button").addEventListener("click", () => this._openDialog());
  }
  attributeChangedCallback() { this._refresh(); }
  _refresh() {
    this.garmentUrl = this.getAttribute("garment-url") || "";
    this.apiEndpoint = this.getAttribute("api-endpoint") || "/api/tryon";
    this.text = this.getAttribute("text") || "Try on";
    const btn = this.shadowRoot.querySelector("button");
    btn.textContent = this.text;
    btn.disabled = !this.garmentUrl;
    btn.title = this.garmentUrl ? "Upload a photo and try this on" : "Missing garment-url";
  }
  _openDialog() {
    if (!this.garmentUrl) return alert("Missing garment-url attribute");
    const backdrop = document.createElement("div");
    backdrop.className = "dialog-backdrop";
    backdrop.innerHTML = `
      <div class="dialog" role="dialog" aria-modal="true" aria-label="Virtual try-on">
        <div class="header">
          <h2>Virtual try-on</h2>
          <button class="close" aria-label="Close">×</button>
        </div>
        <div class="body">
          <div class="upload" aria-live="polite">
            <input type="file" accept="image/*" aria-label="Upload your photo" />
            <p>Upload a clear, front-facing photo (upper body). We won't store it longer than necessary.</p>
          </div>
          <div class="preview" hidden>
            <div>
              <div class="canvas-wrap"><canvas id="person"></canvas></div>
              <div class="controls"><span>Brush:</span>
                <input type="range" min="5" max="60" value="24" id="brush" />
                <label class="input"><input type="checkbox" id="maskToggle" /> Mask clothing area</label>
              </div>
            </div>
            <div>
              <img id="garment" style="max-width:100%; border-radius:8px; border:1px solid #eee" alt="Garment" />
            </div>
          </div>
          <div class="progress" id="progress" aria-live="polite"></div>
          <div class="error" id="error" role="alert"></div>
        </div>
        <div class="footer">
          <button class="primary" id="run" disabled>Generate</button>
        </div>
      </div>`;
    const close = () => backdrop.remove();
    backdrop.querySelector(".close").addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
    document.addEventListener("keydown", function esc(ev) { if (ev.key === "Escape") { close(); document.removeEventListener("keydown", esc); } });
    document.body.append(backdrop);

    const fileInput = backdrop.querySelector('input[type=file]');
    const canvas = backdrop.querySelector('#person');
    const ctx = canvas.getContext('2d');
    const garmentImg = backdrop.querySelector('#garment');
    garmentImg.src = this.garmentUrl;

    const maskToggle = backdrop.querySelector('#maskToggle');
    const brush = backdrop.querySelector('#brush');
    let drawing = false;

    fileInput.onchange = async () => {
      const f = fileInput.files?.[0];
      if (!f) return;
      const url = URL.createObjectURL(f);
      const img = await loadImage(url);
      const { w, h } = fitContain(img.width, img.height, 480, 640);
      canvas.width = w; canvas.height = h;
      ctx.clearRect(0,0,w,h);
      ctx.drawImage(img, 0, 0, w, h);
      const mask = document.createElement("canvas"); mask.width=w; mask.height=h;
      const mctx = mask.getContext("2d");
      mctx.fillStyle = "rgba(255,0,0,0.6)";
      const preview = backdrop.querySelector(".preview"); preview.hidden = false;
      const runBtn = backdrop.querySelector("#run"); runBtn.disabled=false;

      canvas.onpointerdown = (e) => { if (!maskToggle.checked) return; drawing = true; draw(e); };
      canvas.onpointermove = (e) => { if (!maskToggle.checked || !drawing) return; draw(e); };
      canvas.onpointerup = () => drawing = false;

      function draw(e) {
        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (w / rect.width);
        const y = (e.clientY - rect.top) * (h / rect.height);
        mctx.beginPath();
        mctx.arc(x, y, +brush.value, 0, Math.PI*2);
        mctx.fill();
        ctx.drawImage(img, 0, 0, w, h);
        ctx.drawImage(mask, 0, 0);
      }

      runBtn.onclick = async () => {
        const progress = backdrop.querySelector("#progress");
        const errEl = backdrop.querySelector("#error"); errEl.textContent = "";
        progress.textContent = "Uploading…";

        const blob = await new Promise(res => canvas.toBlob(b => res(b), "image/jpeg", 0.92));

        const fd = new FormData();
        fd.append("person", new File([blob], "person.jpg", { type: "image/jpeg" }));
        fd.append("garmentUrl", this.garmentUrl);
        fd.append("category", inferCategoryFromUrl(this.garmentUrl));

        try {
          const r = await fetch(this.apiEndpoint, { method: "POST", body: fd });
          if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
          progress.textContent = "Generating…";
          const data = await r.json();
          progress.textContent = "Done.";
          const im = document.createElement("img");
          im.src = data.imageUrl; im.alt = "Try-on result";
          im.style.maxWidth = "100%"; im.style.borderRadius = "8px"; im.style.border = "1px solid #eee";
          garmentImg.parentElement.replaceChildren(im);
        } catch (e) {
          progress.textContent = "";
          errEl.textContent = e?.message || String(e);
        }
      };
    };
  }
}

customElements.define("tryon-button", TryOnButton);

function loadImage(url) {
  return new Promise((res, rej) => { const i = new Image(); i.onload=() => res(i); i.onerror=rej; i.src=url; });
}
function fitContain(sw, sh, maxW, maxH) {
  const r = Math.min(maxW/sw, maxH/sh);
  return { w: Math.round(sw*r), h: Math.round(sh*r) };
}
function inferCategoryFromUrl(u) {
  const s = u.toLowerCase();
  if (/(coat|jacket|parka|blazer|trench)/.test(s)) return "outerwear";
  if (/(dress|gown|maxi|midi)/.test(s)) return "dress";
  if (/(jeans|trousers|pants|skirt|shorts)/.test(s)) return "bottom";
  return "top";
}
