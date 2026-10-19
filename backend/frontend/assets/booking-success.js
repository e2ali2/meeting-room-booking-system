window.showBookingSuccess = booking => {
  const room = roomBy(booking.room_id);
  const office = officeBy(room.office_id);
  openModal('Встреча запланирована', '', `
    <div class="booking-success-content">
      <div class="booking-success-check" aria-hidden="true"><svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="36"/><path d="M23 41l11 11 24-25"/></svg></div>
      <p class="booking-success-eyebrow">ВСЁ ГОТОВО</p>
      <h4>Место для встречи — за вами.</h4>
      <p class="booking-success-intro">Бронь подтверждена. До встречи в ${esc(room.name || 'переговорной')}!</p>
      <div class="booking-success-ticket">
        <div class="success-ticket-top"><b>${esc(room.name || 'Переговорная')}</b><span>Подтверждено</span></div>
        <p>${esc(office.name || 'Офис')} · ${esc(room.floor || '—')} этаж</p>
        <div class="success-ticket-date"><span>${esc(fmtDate(booking.start_time))}</span><strong>${esc(fmtTime(booking.start_time))} — ${esc(fmtTime(booking.end_time))}<small>МСК</small></strong></div>
      </div>
      <p class="booking-success-note">Адрес для уведомлений: <b>${esc(booking.notification_email || '')}</b></p>
      <button type="button" class="btn" id="success-my-bookings">Мои бронирования <span aria-hidden="true">→</span></button>
    </div>
  `);
  const modal=document.querySelector('#modal-root .modal');
  modal.classList.add('booking-success-modal');
  modal.querySelector('h3').id='booking-success-title';
  modal.setAttribute('aria-labelledby','booking-success-title');
  modal.querySelector('.modal-head button').setAttribute('aria-label','Закрыть подтверждение');
  const button=document.getElementById('success-my-bookings');
  button.onclick=()=>{closeModal();navigate('bookings');};
  button.focus({preventScroll:true});
};

document.addEventListener('keydown',event=>{
  const modal=document.querySelector('.booking-success-modal');
  if(!modal)return;
  if(event.key==='Escape'){event.preventDefault();closeModal();}
  if(event.key==='Tab'){
    const buttons=[...modal.querySelectorAll('button')];
    if(event.shiftKey&&document.activeElement===buttons[0]){event.preventDefault();buttons.at(-1).focus();}
    if(!event.shiftKey&&document.activeElement===buttons.at(-1)){event.preventDefault();buttons[0].focus();}
  }
});

document.addEventListener('click',event=>{
  const home=event.target.closest('[data-home]');
  if(!home||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();
  closeModal();
  window.closeDateTimePicker?.();
  document.querySelector('.sidebar')?.classList.remove('open');
  state.page=null;
  document.getElementById('workspace').classList.add('hidden');
  document.getElementById('landing').classList.remove('hidden');
  try{window.history.replaceState({},'',window.location.pathname);}catch{}
  window.scrollTo({top:0,behavior:'smooth'});
  document.querySelector('#landing [data-home]')?.focus({preventScroll:true});
});
