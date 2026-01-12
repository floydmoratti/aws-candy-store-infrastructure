const API_URL = "/products/mock/products.json";

function setupBuyButtons() {
  document.querySelectorAll('.buy-btn').forEach(button => {
    button.addEventListener('click', () => {
      if (button.disabled) return;

      const url = button.dataset.url;
      if (url) {
        window.location.href = url;
      }
    });
  });
}

async function updateButtons() {
  const products = document.querySelectorAll('.product');
  if (!products.length) return;

  try {
    const response = await fetch(API_URL);
    if (!response.ok) throw new Error('Mock API error');

    const data = await response.json();

    products.forEach(product => {
      const productId = product.dataset.id;
      const button = product.querySelector('.buy-btn');

      if (data[productId] && data[productId].quantity === 0) {
        button.textContent = "Sold Out";
        button.disabled = true;
        button.classList.add('disabled');
      }
    });
  } catch (err) {
    console.error(err);
  }
}


document.addEventListener('DOMContentLoaded', () => {
  setupBuyButtons();
  updateButtons();
});
