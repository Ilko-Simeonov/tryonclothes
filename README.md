# NanoBanana Try-On (VTON) — Python/FastAPI

Adds a **Try On** button to your product pages and calls a minimal **FastAPI** service to generate a realistic preview of your garment on a shopper’s uploaded photo, using Google’s **Nano Banana** (Gemini 2.5 Flash Image) hosted on **fal.ai**.

- ⚙️ Front-end: framework-agnostic Web Component `<tryon-button>`.
- 🔒 Keys stay server-side (`FAL_KEY`).
- 🖼️ Input: a garment image URL (flat/ghost mannequin, white bg is best).
- 👤 User: front-facing upper-body selfie; optional masking (UI built-in).
- ♿ Accessible modal (ESC, focus trap, ARIA).
- 🧹 Privacy: EXIF stripped, resized, auto-delete after TTL.

## Quick start

**Requirements**: Python 3.11+, pip, virtualenv

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env


Embed on your product page


<script type="module" src="https://YOUR-BACKEND/frontend/tryon-widget.js"></script>
<tryon-button
  garment-url="https://cdn.yourshop.example/images/sku1234_frontal.png"
  api-endpoint="https://YOUR-BACKEND/api/tryon"
  text="Try on">
</tryon-button>
