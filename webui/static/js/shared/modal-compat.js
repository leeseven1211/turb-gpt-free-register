// Shared legacy account log/QR windows. Vue dialogs have their own shared owner.
(() => {
  let scrollY = 0;
  window.updateModalScrollLock = () => {
    const open = ['liveLogPanel','qrPanel','accountDetailDrawer','emailChangeModal'].some(id => {
      const panel = document.getElementById(id);
      return panel && !panel.closest('.hidden,[hidden]');
    });
    const locked = document.body.classList.contains('modal-open');
    if (open && !locked) {
      scrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.body.style.top = `-${scrollY}px`;
      document.body.classList.add('modal-open');
      document.documentElement.style.overflow = 'hidden';
    } else if (!open && locked) {
      document.body.classList.remove('modal-open');
      document.body.style.top = '';
      document.documentElement.style.overflow = '';
      window.scrollTo(0,scrollY);
    }
  };
  window.closeLiveLogModal = () => {
    liveLogEmail = null; clearInterval(liveLogTimer);
    document.getElementById('liveLogPanel')?.classList.add('hidden');
    window.updateModalScrollLock();
  };
  window.openQrModal = url => {
    const panel = document.getElementById('qrPanel'), image = document.getElementById('qrImage'), link = document.getElementById('qrOpenLink');
    if (!panel || !image || !link) return;
    image.src = String(url || ''); link.href = String(url || ''); link.textContent = String(url || '');
    panel.classList.remove('hidden'); window.updateModalScrollLock();
    document.getElementById('btnCloseQrPanel')?.focus({preventScroll:true});
  };
  window.closeQrModal = () => {
    document.getElementById('qrPanel')?.classList.add('hidden');
    document.getElementById('qrImage')?.removeAttribute('src'); window.updateModalScrollLock();
  };
  document.addEventListener('keydown',event => {
    if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
    const live = document.getElementById('liveLogPanel'), qr = document.getElementById('qrPanel');
    if (live && !live.closest('.hidden,[hidden]')) window.closeLiveLogModal();
    else if (qr && !qr.closest('.hidden,[hidden]')) window.closeQrModal();
  });
})();
