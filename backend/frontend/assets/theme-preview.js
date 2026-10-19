// A reversible preview: ?theme=classic shows the exact previous visual layer.
if (new URLSearchParams(window.location.search).get('theme') === 'classic') {
  const stylesheet = document.getElementById('premium-theme');
  if (stylesheet) stylesheet.disabled = true;
}
