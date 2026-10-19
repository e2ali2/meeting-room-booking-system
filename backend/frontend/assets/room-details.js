(() => {
  const stories = {
    Atlas: {
      lead: 'Большие идеи начинаются за одним столом.',
      text: 'Atlas — пространство для встреч большой команды, презентаций и совместного планирования. Тёплое дерево и глубокие зелёные оттенки задают спокойный ритм: здесь удобно собрать участников, разложить идеи и прийти к общему решению.',
      uses: ['Презентации', 'Командные встречи', 'Стратегические сессии'],
      photo: 'atlas'
    },
    Vega: {
      lead: 'Место, где разговор превращается в решение.',
      text: 'Vega создана для рабочих обсуждений в комфортном кругу. Лаконичный интерьер, общий стол и мягкая цветовая палитра помогают сосредоточиться на главном — обсудить проект, разобрать задачу или провести встречу с партнёрами.',
      uses: ['Проектные обсуждения', 'Встречи с партнёрами', 'Мозговые штурмы'],
      photo: 'vega'
    },
    Orion: {
      lead: 'Больше света. Больше пространства для мысли.',
      text: 'Orion — камерная переговорная для содержательных разговоров и небольших команд. Светлый интерьер и зелень за окнами создают лёгкое настроение. Хороший выбор для интервью, короткой планёрки или совместной работы над новой идеей.',
      uses: ['Интервью', 'Планёрки', 'Видеовстречи'],
      photo: 'orion'
    },
    Polaris: {
      lead: 'Ваш ориентир для спокойной продуктивной встречи.',
      text: 'Polaris — уютное пространство Северного офиса для небольших встреч. Зелёные акценты и сдержанный интерьер поддерживают атмосферу собранности: удобно обсудить детали, провести встречу один на один или синхронизироваться с коллегами.',
      uses: ['Встречи один на один', 'Небольшие команды', 'Рабочие обсуждения'],
      photo: 'polaris'
    }
  };
  let returnFocus = null;
  const originalClose = window.closeModal;
  window.closeModal = () => {
    const wasDetails = !!document.querySelector('.room-details-modal');
    originalClose();
    if (wasDetails && returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
  };
  window.openRoomDetails = id => {
    const room = state.rooms.find(r => r.room_id === id);
    if (!room) return;
    returnFocus = document.activeElement;
    const office = officeBy(room.office_id);
    const story = stories[room.name] || {
      lead:'Пространство для ваших идей.',
      text:'Переговорная для совместной работы, встреч и обсуждения проектов. Выберите удобное время и соберите команду за одним столом.',
      uses:['Рабочие встречи','Обсуждение проектов'],photo:'atlas'
    };
    const available = state.page === 'search' && state.searchContext && state.searchResults?.some(r => r.room_id === id);
    const photo = room.photo_url || `/assets/rooms/${story.photo}.jpg`;
    const equipment = (room.equipment || []).map(e => `<span>${equipmentIcon(e.name)} ${esc(equipmentName(e.name))}</span>`).join('');
    const time = available ? `${fmtDate(state.searchContext.start_time)} · ${fmtTime(state.searchContext.start_time)}–${fmtTime(state.searchContext.end_time)} МСК` : 'Выберите дату и время, чтобы проверить доступность.';
    openModal(room.name, office.name || 'Переговорная', `
      <div class="room-detail-hero"><img src="${esc(photo)}" alt="Интерьер переговорной ${esc(room.name)}" onerror="this.remove()"><span>ПРОСТРАНСТВО ДЛЯ ВСТРЕЧ</span></div>
      <div class="room-detail-content">
        <div class="room-detail-facts"><div><small>Вместимость</small><b>До ${esc(room.capacity)} человек</b></div><div><small>Расположение</small><b>${esc(room.floor)} этаж</b></div><div><small>Статус комнаты</small><b>${room.status === 'ACTIVE' ? 'Доступна для бронирования' : 'Неактивна'}</b></div></div>
        <h4>${esc(story.lead)}</h4><p class="room-detail-description">${esc(story.text)}</p>
        <div class="room-detail-tags">${story.uses.map(t=>`<span>${esc(t)}</span>`).join('')}</div>
        <section class="room-detail-section"><h5>Всё для вашей встречи</h5><div class="room-detail-equipment">${equipment || '<span>Стандартное оснащение</span>'}</div></section>
        <section class="room-detail-section room-detail-address"><span aria-hidden="true">⌖</span><div><h5>${esc(office.name || 'Офис')}</h5><p>${esc(office.address || 'Адрес уточняется')} · ${esc(room.floor)} этаж</p></div></section>
        <section class="room-detail-rules"><h5>Перед бронированием</h5><p>Встречи от 15 минут до 4 часов, шаг — 15 минут. Время указано по Москве. Изменить или отменить свою бронь можно не позднее чем за 30 минут до начала.</p></section>
      </div><footer class="room-detail-footer"><div><b>${available?'Свободна в выбранное время':'Спланируйте встречу'}</b><p>${esc(time)}</p></div><button type="button" class="btn" id="room-detail-action">${available?'Забронировать':'Выбрать время'} →</button></footer>
    `);
    const modal = document.querySelector('#modal-root .modal');
    modal.classList.add('room-details-modal');
    modal.querySelector('h3').id = 'room-detail-title';
    modal.setAttribute('aria-labelledby','room-detail-title');
    modal.querySelector('.modal-head button').setAttribute('aria-label','Закрыть описание');
    modal.querySelector('.modal-head button').focus({preventScroll:true});
    document.getElementById('room-detail-action').onclick = () => {
      closeModal();
      if (available) return openBooking(id);
      if (state.page !== 'search') navigate('search');
      const form = document.getElementById('search-form');
      if (form) {
        const select = form.querySelector('[name="office_id"]');
        select.value = room.office_id;
        select.dispatchEvent(new Event('change',{bubbles:true}));
        form.scrollIntoView({behavior:'smooth',block:'center'});
        form.querySelector('[data-datetime-picker]')?.focus({preventScroll:true});
      }
      toast('Выберите время и нажмите «Найти комнату»');
    };
  };
  document.addEventListener('click',event=>{
    const card=event.target.closest('[data-room-details]');
    if (card && !event.target.closest('button,a,input,select')) openRoomDetails(card.dataset.roomDetails);
  });
  document.addEventListener('keydown',event=>{
    const modal=document.querySelector('.room-details-modal');
    if (modal && event.key==='Escape') {event.preventDefault();closeModal();return;}
    if (modal && event.key==='Tab') {
      const controls=[...modal.querySelectorAll('button,a[href],input,select,[tabindex="0"]')].filter(el=>!el.disabled);
      const first=controls[0],last=controls[controls.length-1];
      if (event.shiftKey && document.activeElement===first) {event.preventDefault();last.focus();}
      if (!event.shiftKey && document.activeElement===last) {event.preventDefault();first.focus();}
    }
    if ((event.key==='Enter'||event.key===' ') && event.target.matches('[data-room-details]')) {
      event.preventDefault();openRoomDetails(event.target.dataset.roomDetails);
    }
  });
})();
