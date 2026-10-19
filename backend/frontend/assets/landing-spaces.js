(() => {
  const grid=document.getElementById('landing-room-grid');
  const photos={Atlas:'atlas',Vega:'vega',Orion:'orion',Polaris:'polaris'};
  async function loadSpaces(){
    try{
      const [rooms,offices]=await Promise.all([api('/rooms'),api('/offices')]);
      if(!state.rooms.length)state.rooms=rooms;
      if(!state.offices.length)state.offices=offices;
      if(!rooms.length){grid.innerHTML='<p class="landing-rooms-loading">Новые пространства скоро появятся.</p>';return;}
      grid.innerHTML=rooms.slice(0,4).map(room=>{
        const office=offices.find(o=>o.office_id===room.office_id);
        const photo=room.photo_url||`/assets/rooms/${photos[room.name]||'atlas'}.jpg`;
        return `<button type="button" class="landing-room-preview" data-preview-room="${esc(room.room_id)}" aria-label="Подробнее о переговорной ${esc(room.name)}"><div class="landing-room-image"><img src="${esc(photo)}" alt="Интерьер переговорной ${esc(room.name)}" loading="lazy" width="1000" height="667" onerror="this.remove()"></div><div class="landing-room-title"><b>${esc(room.name)}</b><span aria-hidden="true">↗</span></div><p>До ${esc(room.capacity)} человек · ${esc(room.floor)} этаж</p><small>${esc(office?.name||'Офис')}</small></button>`;
      }).join('');
      const featured=rooms.find(room=>room.name==='Atlas')||rooms[0];
      document.getElementById('hero-room-name').textContent=featured.name;
      document.getElementById('hero-room-meta').textContent=`До ${featured.capacity} человек · ${featured.floor} этаж`;
      const heroImage=document.querySelector('.hero-room-photo>img');
      heroImage.src=featured.photo_url||`/assets/rooms/${photos[featured.name]||'atlas'}.jpg`;
      heroImage.alt=`Переговорная ${featured.name}`;
      document.getElementById('landing-spaces-count').textContent=`${rooms.length} пространства · ${new Set(rooms.map(r=>r.office_id)).size} офиса`;
    }catch{
      grid.innerHTML='<p class="landing-rooms-loading">Не удалось загрузить пространства. <button type="button" class="btn secondary small" id="retry-spaces">Повторить</button></p>';
      document.getElementById('retry-spaces').onclick=loadSpaces;
    }
  }
  grid.addEventListener('click',event=>{
    const button=event.target.closest('[data-preview-room]');
    if(button)openRoomDetails(button.dataset.previewRoom);
  });
  loadSpaces();
})();
