# Try-On Clothes Integration Guide

## Quick Start

### 1. Basic Integration

Add this single line to your website's HTML:

```html
<script src="https://tryonclothes.onrender.com/frontend/tryon-widget.js"></script>
```

### 2. Add Try-On Buttons

Place try-on buttons next to your products:

```html
<tryon-button 
  garment-url="https://yourstore.com/images/product.jpg" 
  garment-name="Product Name" 
  garment-price="29.99"
  text="Try On">
</tryon-button>
```

## Complete Integration Examples

### E-commerce Product Page

```html
<!DOCTYPE html>
<html>
<head>
    <title>Product Page</title>
    <script src="https://tryonclothes.onrender.com/frontend/tryon-widget.js"></script>
</head>
<body>
    <div class="product-page">
        <div class="product-images">
            <img src="product-main.jpg" alt="Product">
        </div>
        
        <div class="product-info">
            <h1>Blue Cotton Shirt</h1>
            <p class="price">$29.99</p>
            <p class="description">Comfortable cotton shirt perfect for everyday wear.</p>
            
            <!-- Try-On Button -->
            <tryon-button 
                garment-url="https://yourstore.com/images/blue-shirt.jpg" 
                garment-name="Blue Cotton Shirt" 
                garment-price="29.99"
                text="Try This Shirt">
            </tryon-button>
            
            <button class="add-to-cart">Add to Cart</button>
        </div>
    </div>
</body>
</html>
```

### Multi-Item Basket System

```html
<!DOCTYPE html>
<html>
<head>
    <title>Product Catalog</title>
    <script src="https://tryonclothes.onrender.com/frontend/tryon-widget.js"></script>
    <script src="https://tryonclothes.onrender.com/frontend/basket-widget.html"></script>
</head>
<body>
    <div class="product-grid">
        <div class="product-card">
            <img src="shirt1.jpg" alt="Shirt 1">
            <h3>Casual Shirt</h3>
            <p>$24.99</p>
            <tryon-button 
                garment-url="shirt1.jpg" 
                garment-name="Casual Shirt" 
                garment-price="24.99"
                text="Try On">
            </tryon-button>
        </div>
        
        <div class="product-card">
            <img src="shirt2.jpg" alt="Shirt 2">
            <h3>Formal Shirt</h3>
            <p>$39.99</p>
            <tryon-button 
                garment-url="shirt2.jpg" 
                garment-name="Formal Shirt" 
                garment-price="39.99"
                text="Try On">
            </tryon-button>
        </div>
    </div>
</body>
</html>
```

## Platform-Specific Integration

### Shopify

1. **Add to theme.liquid:**
```liquid
<!-- In your theme's theme.liquid file, before </head> -->
<script src="https://tryonclothes.onrender.com/frontend/tryon-widget.js"></script>
```

2. **Add to product template:**
```liquid
<!-- In your product template -->
<tryon-button 
  garment-url="{{ product.featured_image | img_url: '800x800' }}" 
  garment-name="{{ product.title }}" 
  garment-price="{{ product.price | money_without_currency }}"
  text="Try On">
</tryon-button>
```

### WooCommerce

1. **Add to functions.php:**
```php
function add_tryon_script() {
    wp_enqueue_script('tryon-widget', 'https://tryonclothes.onrender.com/frontend/tryon-widget.js', array(), '1.0.0', true);
}
add_action('wp_enqueue_scripts', 'add_tryon_script');
```

2. **Add to single-product.php:**
```php
<tryon-button 
  garment-url="<?php echo wp_get_attachment_image_url(get_post_thumbnail_id(), 'large'); ?>" 
  garment-name="<?php the_title(); ?>" 
  garment-price="<?php echo $product->get_price(); ?>"
  text="Try On">
</tryon-button>
```

### Magento

1. **Add to default.xml:**
```xml
<page xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="urn:magento:framework:View/Layout/etc/page_configuration.xsd">
    <head>
        <script src="https://tryonclothes.onrender.com/frontend/tryon-widget.js"/>
    </head>
</page>
```

2. **Add to product view template:**
```html
<tryon-button 
  garment-url="<?= $block->getImage($product, 'product_page_image_large')->getImageUrl() ?>" 
  garment-name="<?= $product->getName() ?>" 
  garment-price="<?= $product->getPrice() ?>"
  text="Try On">
</tryon-button>
```

## API Integration

### Custom API Endpoint

```html
<tryon-button 
  garment-url="product.jpg" 
  api-endpoint="https://your-api.com/tryon"
  text="Try On">
</tryon-button>
```

### JavaScript API

```javascript
// Initialize the widget
const tryOnWidget = new TryOnButton();

// Set product data
tryOnWidget.setGarment({
  url: 'product.jpg',
  name: 'Product Name',
  price: '29.99'
});

// Open try-on dialog
tryOnWidget.openDialog();
```

## Styling Customization

### CSS Custom Properties

```css
:root {
  --tryon-primary-color: #007bff;
  --tryon-secondary-color: #6c757d;
  --tryon-border-radius: 8px;
  --tryon-font-family: 'Inter', sans-serif;
}

tryon-button {
  --button-bg: var(--tryon-primary-color);
  --button-color: white;
  --button-border-radius: var(--tryon-border-radius);
}
```

### Custom Button Styles

```css
tryon-button::part(button) {
  background: linear-gradient(45deg, #007bff, #0056b3);
  border: none;
  padding: 12px 24px;
  border-radius: 25px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: all 0.3s ease;
}

tryon-button::part(button):hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}
```

## Advanced Features

### Multi-Item Try-On

```html
<!-- Enable basket functionality -->
<script src="https://tryonclothes.onrender.com/frontend/basket-widget.html"></script>

<!-- Products with basket support -->
<tryon-button 
  garment-url="item1.jpg" 
  garment-name="Item 1" 
  garment-price="29.99"
  text="Add to Try-On Basket">
</tryon-button>
```

### Custom Categories

```html
<tryon-button 
  garment-url="product.jpg" 
  garment-name="Product" 
  garment-price="29.99"
  category="outerwear"
  text="Try On">
</tryon-button>
```

### Custom Prompts

```html
<tryon-button 
  garment-url="product.jpg" 
  garment-name="Product" 
  garment-price="29.99"
  prompt-extra="Make it look casual and relaxed"
  text="Try On">
</tryon-button>
```

## Troubleshooting

### Common Issues

1. **Widget not loading:**
   - Check if the script URL is accessible
   - Verify there are no JavaScript errors in console
   - Ensure the script is loaded before using the widget

2. **Images not displaying:**
   - Verify image URLs are accessible
   - Check CORS settings if images are on different domains
   - Ensure images are in supported formats (JPEG, PNG, WebP)

3. **Try-on not working:**
   - Check API endpoint configuration
   - Verify API key is set correctly
   - Check network connectivity

### Browser Support

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

### Mobile Support

The widget is fully responsive and works on:
- iOS Safari 12+
- Chrome Mobile 60+
- Samsung Internet 8+

## Support

For technical support or questions:
- Email: support@tryonclothes.com
- Documentation: https://tryonclothes.onrender.com/docs
- GitHub: https://github.com/tryonclothes/widget 