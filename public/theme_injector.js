(function () {
  function injectBrand() {
    var headerLeft = document.querySelector('#header > div.flex.items-center');
    if (!headerLeft) return false;
    if (headerLeft.querySelector('.jonaki-brand')) return true;

    var brand = document.createElement('div');
    brand.className = 'jonaki-brand';
    brand.style.display = 'flex';
    brand.style.alignItems = 'center';
    brand.style.gap = '8px';
    brand.style.marginLeft = '8px';

    var icon = document.createElement('img');
    icon.src = '/public/firefly_logo.svg';
    icon.alt = 'Jonaki';
    icon.style.width = '24px';
    icon.style.height = '24px';
    icon.style.filter = 'drop-shadow(0 0 5px rgba(247,252,167,0.5))';

    var text = document.createElement('span');
    text.textContent = 'Jonaki';
    text.style.color = '#F7FCA7';
    text.style.fontWeight = '600';
    text.style.fontSize = '16px';
    text.style.textShadow = '0 0 8px rgba(247,252,167,0.35)';

    brand.appendChild(icon);
    brand.appendChild(text);
    headerLeft.appendChild(brand);
    return true;
  }

  var tries = 0;
  var interval = setInterval(function () {
    tries++;
    if (injectBrand() || tries > 40) {
      clearInterval(interval);
    }
  }, 250);

  var observer = new MutationObserver(function () {
    injectBrand();
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
