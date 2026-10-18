// Keep native form values while rendering a consistent, keyboard-accessible menu.
(() => {
  let active = null;
  let serial = 0;
  const close = (focus = false) => {
    if (!active) return;
    const {button, menu} = active;
    active = null;
    menu.remove();
    button.setAttribute('aria-expanded', 'false');
    if (focus && button.isConnected) button.focus();
  };
  const position = () => {
    if (!active) return;
    const {button, menu} = active;
    if (!button.isConnected) return close();
    const box = button.getBoundingClientRect();
    const width = Math.min(Math.max(box.width, 290), window.innerWidth - 24);
    menu.style.width = `${width}px`;
    menu.style.left = `${Math.max(12, Math.min(box.left, window.innerWidth - width - 12))}px`;
    const below = window.innerHeight - box.bottom - 16;
    const above = box.top - 16;
    const upwards = below < 180 && above > below;
    menu.style.maxHeight = `${Math.max(60, Math.min(280, upwards ? above : below))}px`;
    menu.style.top = upwards ? 'auto' : `${box.bottom + 7}px`;
    menu.style.bottom = upwards ? `${window.innerHeight - box.top + 7}px` : 'auto';
  };
  const enhance = select => {
    if (select.multiple || select.size > 1 || select.closest('.space-select')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'space-select';
    select.before(wrapper);
    wrapper.append(select);
    select.classList.add('space-select-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'space-select-trigger';
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    const menuId = `space-options-${++serial}`;
    button.setAttribute('aria-controls', menuId);
    const label = select.closest('.field')?.querySelector('label')?.textContent || 'Выберите значение';
    const caption = document.createElement('span');
    caption.className = 'space-select-caption';
    const arrow = document.createElement('span');
    arrow.className = 'space-select-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    button.append(caption, arrow);
    wrapper.append(button);
    const sync = () => {
      caption.textContent = select.selectedOptions[0]?.textContent || 'Выберите';
      button.disabled = select.disabled;
      button.setAttribute('aria-label', `${label}: ${caption.textContent}`);
    };
    sync();
    select.addEventListener('change', sync);
    const open = () => {
      close();
      const menu = document.createElement('div');
      menu.id = menuId;
      menu.className = 'space-select-menu';
      menu.setAttribute('role', 'listbox');
      menu.setAttribute('aria-label', label);
      const options = Array.from(select.options).map((option, index) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'space-select-option';
        item.tabIndex = -1;
        item.textContent = option.textContent;
        item.disabled = option.disabled;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', String(option.selected));
        item.onclick = () => {
          select.selectedIndex = index;
          select.dispatchEvent(new Event('input', {bubbles: true}));
          select.dispatchEvent(new Event('change', {bubbles: true}));
          sync();
          close(true);
        };
        menu.append(item);
        return item;
      });
      document.body.append(menu);
      active = {button, menu};
      button.setAttribute('aria-expanded', 'true');
      position();
      const enabled = options.filter(o => !o.disabled);
      (options[select.selectedIndex]?.disabled ? enabled[0] : options[select.selectedIndex] || enabled[0])?.focus();
      menu.onkeydown = event => {
        const index = enabled.indexOf(document.activeElement);
        let next;
        if (event.key === 'ArrowDown') next = (index + 1) % enabled.length;
        if (event.key === 'ArrowUp') next = (index - 1 + enabled.length) % enabled.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = enabled.length - 1;
        if (next !== undefined) {event.preventDefault(); enabled[next]?.focus();}
        if (event.key === 'Escape') {event.preventDefault(); close(true);}
        if (event.key === 'Tab') close(true);
      };
    };
    button.onclick = () => active?.button === button ? close() : open();
    button.onkeydown = event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {event.preventDefault(); open();}
    };
  };
  const scan = () => {
    if (active && !active.button.isConnected) close();
    document.querySelectorAll('select').forEach(enhance);
  };
  document.addEventListener('pointerdown', event => {
    if (active && !active.menu.contains(event.target) && !active.button.contains(event.target)) close();
  });
  window.addEventListener('resize', position);
  window.addEventListener('scroll', () => {if (active) position();}, true);
  new MutationObserver(scan).observe(document.body, {childList: true, subtree: true});
  scan();
})();
