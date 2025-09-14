// MIT License — Enhanced NanoBanana Try-On frontend with basket functionality

const template = document.createElement("template");
template.innerHTML = `
  <style>@import url('https://tryonclothes.onrender.com/frontend/styles.css');</style>
  <button class="tryon-btn" part="button" aria-haspopup="dialog"></button>
`;

class TryOnButton extends HTMLElement {
  static get observedAttributes() { return ["garment-url", "api-endpoint", "text", "garment-name", "garment-price"]; }
  
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.append(template.content.cloneNode(true));
    this.apiEndpoint = "/api/tryon";
    this.text = "Try on";
    this.garmentName = "";
    this.garmentPrice = "";
    
    // Initialize basket if it doesn't exist
    if (!window.tryOnBasket) {
      window.tryOnBasket = {
        items: [],
        addItem: function(item) {
          if (!this.items.find(i => i.url === item.url)) {
            this.items.push(item);
            this.updateBasketUI();
          }
        },
        removeItem: function(url) {
          this.items = this.items.filter(i => i.url !== url);
          this.updateBasketUI();
        },
        clear: function() {
          this.items = [];
          this.updateBasketUI();
        },
        updateBasketUI: function() {
          const basketBtn = document.querySelector('.basket-button');
          if (basketBtn) {
            const count = this.items.length;
            basketBtn.textContent = count > 0 ? `Basket (${count})` : 'Basket';
            basketBtn.style.display = count > 0 ? 'block' : 'none';
          }
        }
      };
    }
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
    this.garmentName = this.getAttribute("garment-name") || "";
    this.garmentPrice = this.getAttribute("garment-price") || "";
    
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
          <h2>Virtual Try-On</h2>
          <div class="header-actions">
            <button class="basket-button" id="basketBtn" style="display: none;">Basket (0)</button>
            <button class="close" aria-label="Close">×</button>
          </div>
        </div>
        <div class="body">
          <div class="upload" aria-live="polite">
            <input type="file" accept="image/*" aria-label="Upload your photo" />
            <p>Upload a clear, front-facing photo (upper body). We won't store it longer than necessary.</p>
          </div>
          <div class="preview" hidden>
            <div class="preview-left">
              <div class="canvas-wrap"><canvas id="person"></canvas></div>
              <div class="controls">
                <span>Brush:</span>
                <input type="range" min="5" max="60" value="24" id="brush" />
                <label class="input">
                  <input type="checkbox" id="maskToggle" /> Mask clothing area
                </label>
              </div>
            </div>
            <div class="preview-right">
              <div class="garment-info">
                <img id="garment" style="max-width:100%; border-radius:8px; border:1px solid #eee" alt="Garment" />
                <div class="garment-details">
                  <h3 id="garmentName">${this.garmentName || 'Selected Item'}</h3>
                  <p id="garmentPrice">${this.garmentPrice ? `$${this.garmentPrice}` : ''}</p>
                </div>
                <div class="garment-actions">
                  <button class="add-to-basket" id="addToBasket">Add to Basket</button>
                  <button class="try-single" id="trySingle">Try This Item</button>
                </div>
              </div>
            </div>
          </div>
          <div class="progress" id="progress" aria-live="polite"></div>
          <div class="error" id="error" role="alert"></div>
        </div>
        <div class="footer">
          <button class="secondary" id="tryBasket" disabled>Try All Items in Basket</button>
          <button class="primary" id="run" disabled>Generate</button>
        </div>
      </div>`;
    
    const close = () => backdrop.remove();
    backdrop.querySelector(".close").addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
    document.addEventListener("keydown", function esc(ev) { if (ev.key === "Escape") { close(); document.removeEventListener("keydown", esc); } });
    document.body.append(backdrop);

    // Initialize basket UI
    window.tryOnBasket.updateBasketUI();
    
    const fileInput = backdrop.querySelector('input[type=file]');
    const canvas = backdrop.querySelector('#person');
    const ctx = canvas.getContext('2d');
    const garmentImg = backdrop.querySelector('#garment');
    const garmentName = backdrop.querySelector('#garmentName');
    const garmentPrice = backdrop.querySelector('#garmentPrice');
    
    garmentImg.src = this.garmentUrl;
    garmentName.textContent = this.garmentName || 'Selected Item';
    garmentPrice.textContent = this.garmentPrice ? `$${this.garmentPrice}` : '';

    const maskToggle = backdrop.querySelector('#maskToggle');
    const brush = backdrop.querySelector('#brush');
    const addToBasketBtn = backdrop.querySelector('#addToBasket');
    const trySingleBtn = backdrop.querySelector('#trySingle');
    const tryBasketBtn = backdrop.querySelector('#tryBasket');
    const runBtn = backdrop.querySelector('#run');
    
    let drawing = false;
    let currentImage = null;

    // Add to basket functionality
    addToBasketBtn.addEventListener('click', () => {
      const item = {
        url: this.garmentUrl,
        name: this.garmentName || 'Selected Item',
        price: this.garmentPrice || '',
        image: this.garmentUrl
      };
      window.tryOnBasket.addItem(item);
      addToBasketBtn.textContent = 'Added to Basket ✓';
      addToBasketBtn.disabled = true;
      setTimeout(() => {
        addToBasketBtn.textContent = 'Add to Basket';
        addToBasketBtn.disabled = false;
      }, 2000);
    });

    // Try single item
    trySingleBtn.addEventListener('click', () => {
      if (!currentImage) {
        alert('Please upload a photo first');
        return;
      }
      this._tryOnItems([{url: this.garmentUrl, name: this.garmentName}], currentImage, backdrop);
    });

    // Try all items in basket
    tryBasketBtn.addEventListener('click', () => {
      if (!currentImage) {
        alert('Please upload a photo first');
        return;
      }
      if (window.tryOnBasket.items.length === 0) {
        alert('Basket is empty');
        return;
      }
      this._tryOnItems(window.tryOnBasket.items, currentImage, backdrop);
    });

    // Update basket button state
    const updateBasketButton = () => {
      const count = window.tryOnBasket.items.length;
      tryBasketBtn.disabled = count === 0;
      tryBasketBtn.textContent = count > 0 ? `Try All Items in Basket (${count})` : 'Try All Items in Basket';
    };
    updateBasketButton();

    fileInput.onchange = async () => {
      const f = fileInput.files?.[0];
      if (!f) return;
      const url = URL.createObjectURL(f);
      const img = await loadImage(url);
      currentImage = img;
      const { w, h } = fitContain(img.width, img.height, 480, 640);
      canvas.width = w; canvas.height = h;
      ctx.clearRect(0,0,w,h);
      ctx.drawImage(img, 0, 0, w, h);
      const mask = document.createElement("canvas"); mask.width=w; mask.height=h;
      const mctx = mask.getContext("2d");
      mctx.fillStyle = "rgba(255,0,0,0.6)";
      const preview = backdrop.querySelector(".preview"); preview.hidden = false;
      runBtn.disabled = false;
      trySingleBtn.disabled = false;
      updateBasketButton();

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
        if (!currentImage) return;
        this._tryOnItems([{url: this.garmentUrl, name: this.garmentName}], currentImage, backdrop);
      };
    };
  }

  async _tryOnItems(items, image, backdrop) {
    const progress = backdrop.querySelector("#progress");
    const errEl = backdrop.querySelector("#error"); 
    errEl.textContent = "";
    
    if (items.length === 1) {
      // Single item try-on
      progress.textContent = "Uploading…";
      const blob = await new Promise(res => {
        const canvas = backdrop.querySelector('#person');
        canvas.toBlob(b => res(b), "image/jpeg", 0.92);
      });

      const fd = new FormData();
      fd.append("person", new File([blob], "person.jpg", { type: "image/jpeg" }));
      fd.append("garmentUrl", items[0].url);
      fd.append("category", inferCategoryFromUrl(items[0].url));

      try {
        const r = await fetch(this.apiEndpoint, { method: "POST", body: fd });
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        progress.textContent = "Generating…";
        const data = await r.json();
        progress.textContent = "Done.";
        this._showResult(data.imageUrl, backdrop);
      } catch (e) {
        progress.textContent = "";
        errEl.textContent = e?.message || String(e);
      }
    } else {
      // Multiple items try-on
      progress.textContent = `Trying on ${items.length} items...`;
      
      try {
        const results = [];
        for (let i = 0; i < items.length; i++) {
          progress.textContent = `Processing item ${i + 1} of ${items.length}...`;
          
          const blob = await new Promise(res => {
            const canvas = backdrop.querySelector('#person');
            canvas.toBlob(b => res(b), "image/jpeg", 0.92);
          });

          const fd = new FormData();
          fd.append("person", new File([blob], "person.jpg", { type: "image/jpeg" }));
          fd.append("garmentUrl", items[i].url);
          fd.append("category", inferCategoryFromUrl(items[i].url));

          const r = await fetch(this.apiEndpoint, { method: "POST", body: fd });
          if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
          
          const data = await r.json();
          results.push({
            imageUrl: data.imageUrl,
            item: items[i]
          });
        }
        
        progress.textContent = "Done.";
        this._showMultipleResults(results, backdrop);
      } catch (e) {
        progress.textContent = "";
        errEl.textContent = e?.message || String(e);
      }
    }
  }

  _showResult(imageUrl, backdrop) {
    const garmentImg = backdrop.querySelector('#garment');
    const im = document.createElement("img");
    im.src = imageUrl; 
    im.alt = "Try-on result";
    im.style.maxWidth = "100%"; 
    im.style.borderRadius = "8px"; 
    im.style.border = "1px solid #eee";
    garmentImg.parentElement.replaceChildren(im);
  }

  _showMultipleResults(results, backdrop) {
    const garmentImg = backdrop.querySelector('#garment');
    const container = document.createElement("div");
    container.className = "results-container";
    
    results.forEach((result, index) => {
      const resultDiv = document.createElement("div");
      resultDiv.className = "result-item";
      
      const img = document.createElement("img");
      img.src = result.imageUrl;
      img.alt = `Try-on result for ${result.item.name}`;
      img.style.maxWidth = "100%";
      img.style.borderRadius = "8px";
      img.style.border = "1px solid #eee";
      
      const label = document.createElement("p");
      label.textContent = result.item.name;
      label.style.margin = "8px 0 0 0";
      label.style.fontSize = "12px";
      label.style.textAlign = "center";
      
      resultDiv.appendChild(img);
      resultDiv.appendChild(label);
      container.appendChild(resultDiv);
    });
    
    garmentImg.parentElement.replaceChildren(container);
  }
}

customElements.define("tryon-button", TryOnButton);

function loadImage(url) {
  return new Promise((res, rej) => { const i = new Image(); i.onload=() => res(i); i.onerror=rej; i.src=url; });
}

function fitContain(sw, sh, maxW, maxH) {
  const r = Math.min(maxW/sw, maxH/sh);
  return { w: Math.round(sw*r), h: Math.round(sh*r); }
}

function inferCategoryFromUrl(u) {
  const s = u.toLowerCase();
  if (/(coat|jacket|parka|blazer|trench)/.test(s)) return "outerwear";
  if (/(dress|gown|maxi|midi)/.test(s)) return "dress";
  if (/(jeans|trousers|pants|skirt|shorts)/.test(s)) return "bottom";
  return "top";
}
