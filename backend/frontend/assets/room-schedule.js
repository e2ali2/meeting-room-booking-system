function mountRoomSchedule(root, roomId) {
  const today = localInput(new Date()).slice(0,10);
  const lastDay = localInput(new Date(Date.now()+30*86400000)).slice(0,10);
  const searchDay = state.searchContext ? localInput(state.searchContext.start_time).slice(0,10) : today;
  let day = searchDay >= today && searchDay <= lastDay ? searchDay : today;
  let revision = 0;
  root.innerHTML = `<div class="schedule-heading"><div><h5>Расписание на день</h5><span>Московское время · МСК</span></div><button type="button" class="schedule-today">Сегодня</button></div>
    <div class="schedule-navigation"><button type="button" class="schedule-prev" aria-label="Предыдущий день">‹</button><b class="schedule-date"></b><button type="button" class="schedule-next" aria-label="Следующий день">›</button></div>
    <div class="schedule-result" aria-live="polite"></div>`;
  const result = root.querySelector('.schedule-result');
  const shift = amount => new Date(Date.parse(day+'T12:00:00Z')+amount*86400000).toISOString().slice(0,10);
  const labelTime = minutes => `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`;
  const duration = minutes => `${Math.floor(minutes/60) ? Math.floor(minutes/60)+' ч ' : ''}${minutes%60 ? minutes%60+' мин' : ''}`.trim() || '0 мин';
  async function load() {
    const current = ++revision;
    root.querySelector('.schedule-date').textContent = new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow',day:'numeric',month:'long',weekday:'short'}).format(bookingDate(day+'T12:00'));
    root.querySelector('.schedule-prev').disabled = day <= today;
    root.querySelector('.schedule-next').disabled = day >= lastDay;
    root.querySelector('.schedule-today').disabled = day === today;
    result.setAttribute('aria-busy','true');
    result.innerHTML = '<div class="schedule-loading">Загружаем занятость комнаты…</div>';
    try {
      const data = await api(`/rooms/${encodeURIComponent(roomId)}/schedule?date=${day}`);
      if (!root.isConnected || current !== revision) return;
      const midnight = bookingDate(day+'T00:00').getTime();
      const intervals = data.busy.map(b => [Math.max(0,Math.round((Date.parse(b.start_time)-midnight)/60000)), Math.min(1440,Math.round((Date.parse(b.end_time)-midnight)/60000))]).filter(([a,b])=>b>a).sort((a,b)=>a[0]-b[0]);
      const merged = [];
      intervals.forEach(([a,b])=>{const last=merged[merged.length-1];if(last && a<=last[1])last[1]=Math.max(last[1],b);else merged.push([a,b]);});
      const segments=[];let cursor=0;
      merged.forEach(([a,b])=>{if(a>cursor)segments.push({start:cursor,end:a,busy:false});segments.push({start:a,end:b,busy:true});cursor=b;});
      if(cursor<1440)segments.push({start:cursor,end:1440,busy:false});
      const occupied = merged.reduce((sum,[a,b])=>sum+b-a,0);
      const nowMinutes=(Date.now()-midnight)/60000;
      const blocks=segments.map(s=>`<div class="schedule-segment ${s.busy?'is-busy':'is-free'}" style="left:${s.start/1440*100}%;width:${(s.end-s.start)/1440*100}%" title="${labelTime(s.start)}–${labelTime(s.end)} · ${s.busy?'Занято':'Свободно'}"></div>`).join('');
      result.innerHTML=`<div class="schedule-legend"><span><i class="free-dot"></i>Свободно</span><span><i class="busy-dot"></i>Занято</span></div>
        <div class="schedule-scroll" tabindex="0" aria-label="Шкала занятости с 00:00 до 24:00, прокрутите вправо на узком экране"><div class="schedule-chart"><div class="schedule-ticks">${[0,6,12,18,24].map(h=>`<span style="left:${h/24*100}%">${String(h).padStart(2,'0')}:00</span>`).join('')}</div><div class="schedule-track" role="img" aria-label="За день занято ${duration(occupied)}, свободно ${duration(1440-occupied)}">${blocks}${nowMinutes>=0&&nowMinutes<1440?`<div class="schedule-now" style="left:${nowMinutes/1440*100}%" title="Текущее время"></div>`:''}</div></div></div>
        <div class="schedule-summary">${occupied?`Занято ${duration(occupied)} · свободно ${duration(1440-occupied)}`:'На этот день бронирований пока нет'}</div>
        <div class="schedule-intervals">${segments.map(s=>`<div class="schedule-interval ${s.busy?'is-busy':'is-free'}"><i></i><b>${labelTime(s.start)}–${labelTime(s.end)}</b><span>${s.busy?'Занято':'Свободно'}</span></div>`).join('')}</div>`;
    } catch (error) {
      if (!root.isConnected || current !== revision) return;
      result.innerHTML='<div class="schedule-error">Не удалось загрузить расписание. <button type="button">Повторить</button></div>';
      result.querySelector('button').onclick=load;
    } finally {
      if(current===revision)result.removeAttribute('aria-busy');
    }
  }
  root.querySelector('.schedule-prev').onclick=()=>{if(day>today){day=shift(-1);load();}};
  root.querySelector('.schedule-next').onclick=()=>{if(day<lastDay){day=shift(1);load();}};
  root.querySelector('.schedule-today').onclick=()=>{day=today;load();};
  load();
}
