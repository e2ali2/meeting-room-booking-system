// Keep open booking screens current without interrupting edits or room details.
(() => {
  let refreshing = false;
  async function refresh() {
    if (refreshing || document.hidden || !state.role || document.querySelector('#modal-root .modal')) return;
    if (!['bookings','all-bookings','dashboard'].includes(state.page)) return;
    refreshing = true;
    try {
      if (state.page === 'all-bookings') {
        const bookings = await api('/admin/bookings');
        if (state.page !== 'all-bookings') return;
        state.adminBookings = bookings;
        filterAdminBookings();
      } else if (state.page === 'bookings') {
        const tab = document.querySelector('[data-booking-tab].active')?.dataset.bookingTab;
        await renderMyBookings();
        if (tab === 'past') document.querySelector('[data-booking-tab="past"]')?.click();
      } else {
        await renderDashboard();
      }
    } catch {
      // Preserve the current screen if a background refresh temporarily fails.
    } finally {
      refreshing = false;
    }
  }
  setInterval(refresh, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
