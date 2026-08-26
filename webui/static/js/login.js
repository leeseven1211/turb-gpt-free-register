    (() => {
      const key = 'webui_auth_code';
      const input = document.getElementById('authCodeInput');
      const remember = document.getElementById('rememberAuthCode');
      const toggle = document.getElementById('togglePassword');
      const submit = document.getElementById('loginSubmit');
      const saved = localStorage.getItem(key) || '';
      if (saved) { input.value = saved; remember.checked = true; }
      document.querySelector('form').addEventListener('submit', () => {
        if (remember.checked) localStorage.setItem(key, input.value || '');
        else localStorage.removeItem(key);
        submit.disabled = true;
        submit.textContent = '验证中…';
      });
      toggle.addEventListener('click', () => {
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        toggle.classList.toggle('is-visible', show);
        toggle.setAttribute('aria-label', show ? '隐藏授权码' : '显示授权码');
      });

      document.querySelectorAll('.bg-dots').forEach((grid) => {
        const rows = Number(grid.dataset.rows || 4);
        const cols = Number(grid.dataset.cols || 6);
        const rowMid = (rows - 1) / 2;
        const colMid = (cols - 1) / 2;
        let maxDist = 0;
        const cells = [];
        for (let r = 0; r < rows; r += 1) {
          for (let c = 0; c < cols; c += 1) {
            const dist = Math.hypot(r - rowMid, c - colMid);
            maxDist = Math.max(maxDist, dist);
            cells.push({ dist });
          }
        }
        cells.forEach(({ dist }) => {
          const t = dist / maxDist;
          const size = 7.5 - t * 3.5;
          const opacity = 0.55 - t * 0.3;
          const dot = document.createElement('span');
          dot.style.width = `${size}px`;
          dot.style.height = `${size}px`;
          dot.style.opacity = String(opacity);
          grid.appendChild(dot);
        });
      });
    })();
