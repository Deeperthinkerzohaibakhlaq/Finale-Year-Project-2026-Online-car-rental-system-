/**
 * AutoHire — JazzCash / EasyPaisa demo wallet (adapted from FYP payment-wallet.js)
 */
(function (global) {
  const modalEl = () => document.getElementById('walletPaymentModal');
  let bsModal = null;
  let state = { amount: 0, method: 'easypaisa', mobile: '', reservationData: null };
  let redirectTimer = null;

  const fmtRs = (n) => 'Rs. ' + (Number(n) || 0).toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const maskMobile = (m) => {
    const d = String(m).replace(/\D/g, '');
    if (d.length < 5) return d;
    return d.slice(0, 2) + '******' + d.slice(-3);
  };

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  const setTheme = (method) => {
    const m = modalEl();
    if (!m) return;
    m.classList.remove('theme-ep', 'theme-jc');
    m.classList.add(method === 'jazzcash' ? 'theme-jc' : 'theme-ep');
    const hdr = m.querySelector('.wallet-header');
    if (hdr) {
      hdr.classList.remove('ep', 'jc');
      hdr.classList.add(method === 'jazzcash' ? 'jc' : 'ep');
    }
    const brand = m.querySelector('#walletBrandName');
    if (brand) brand.textContent = method === 'jazzcash' ? 'JazzCash' : 'EasyPaisa';
    m.querySelectorAll('.wallet-btn-next, .wallet-btn-pay, .wallet-btn-waiting').forEach((btn) => {
      btn.classList.remove('ep', 'jc');
      btn.classList.add(method === 'jazzcash' ? 'jc' : 'ep');
    });
  };

  const showStep = (n) => {
    modalEl()?.querySelectorAll('.wallet-step').forEach((el) => {
      el.classList.toggle('is-active', el.dataset.step === String(n));
    });
  };

  const open = (opts) => {
    if (redirectTimer) {
      clearTimeout(redirectTimer);
      redirectTimer = null;
    }
    state = {
      amount: opts.amount,
      method: opts.method || 'easypaisa',
      mobile: '',
      reservationData: opts.reservationData || null
    };
    setTheme(state.method);
    const amtEl = document.getElementById('walletPayAmount');
    if (amtEl) amtEl.textContent = fmtRs(state.amount);
    const mob = document.getElementById('walletMobile');
    const pin = document.getElementById('walletPin');
    if (mob) mob.value = '';
    if (pin) pin.value = '';
    ['walletStep1Error', 'walletStep3Error'].forEach((id) => {
      const e = document.getElementById(id);
      if (e) e.textContent = '';
    });
    const countdown = document.getElementById('walletRedirectCountdown');
    if (countdown) countdown.textContent = '';
    showStep(1);
    if (!bsModal && modalEl() && global.bootstrap) {
      bsModal = new bootstrap.Modal(modalEl(), { backdrop: 'static', keyboard: false });
    }
    bsModal?.show();
  };

  const validateMobile = (raw) => {
    const m = String(raw).replace(/\D/g, '');
    return /^03\d{9}$/.test(m) ? m : null;
  };

  const onNext = async () => {
    const err = document.getElementById('walletStep1Error');
    const raw = (document.getElementById('walletMobile') || {}).value || '';
    const m = validateMobile(raw);
    if (!m) {
      if (err) err.textContent = 'Enter a valid mobile number (03XXXXXXXXX).';
      return;
    }
    state.mobile = m;
    if (err) err.textContent = '';
    const loadMsg = document.getElementById('walletConnectMsg');
    if (loadMsg) loadMsg.textContent = 'Connecting to ' + (state.method === 'jazzcash' ? 'JazzCash' : 'EasyPaisa') + '...';
    showStep(2);
    await wait(1400);
    const msg = document.getElementById('walletOtpMessage');
    const app = state.method === 'jazzcash' ? 'JazzCash' : 'EasyPaisa';
    if (msg) {
      msg.innerHTML = 'Enter the PIN/OTP for your <strong>' + app + '</strong> account<br><strong>' + maskMobile(m) + '</strong>';
    }
    showStep(3);
  };

  const onPay = async () => {
    const err = document.getElementById('walletStep3Error');
    const pin = (document.getElementById('walletPin') || {}).value || '';
    const pinLen = pin.replace(/\D/g, '').length;
    if (pinLen < 4 || pinLen > 5) {
      if (err) err.textContent = 'Invalid PIN. Enter 4 or 5 digits.';
      return;
    }
    if (err) err.textContent = '';
    showStep(4);
    await wait(1800);
    try {
      const resp = await fetch('/process-payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: state.method,
          amount: state.amount,
          fee: 0,
          total: state.amount,
          details: { wallet_mobile: state.mobile },
          reservation_data: state.reservationData
        })
      });
      const data = await resp.json();
      if (!data.success) {
        showStep(3);
        if (err) err.textContent = data.message || 'Payment failed.';
        return;
      }
      const txnEl = document.getElementById('walletSuccessTxn');
      const amtOk = document.getElementById('walletSuccessAmount');
      const methodLbl = document.getElementById('walletSuccessMethod');
      if (txnEl) txnEl.textContent = data.transaction_id || '';
      if (amtOk) amtOk.textContent = fmtRs(state.amount);
      if (methodLbl) methodLbl.textContent = state.method === 'jazzcash' ? 'JazzCash' : 'EasyPaisa';
      const waitBtn = document.getElementById('walletBtnWaiting');
      const url = '/waiting/' + encodeURIComponent(data.reservation_id);
      if (waitBtn) waitBtn.href = url;
      showStep(5);
      let sec = 4;
      const countdown = document.getElementById('walletRedirectCountdown');
      const tick = () => {
        if (countdown) countdown.textContent = 'Redirecting to reservation status in ' + sec + 's...';
        if (sec <= 0) {
          window.location.href = url;
          return;
        }
        sec -= 1;
        redirectTimer = setTimeout(tick, 1000);
      };
      tick();
    } catch (e) {
      showStep(3);
      if (err) err.textContent = 'Network error. Try again.';
    }
  };

  const bind = () => {
    document.getElementById('walletBtnNext')?.addEventListener('click', onNext);
    document.getElementById('walletBtnPay')?.addEventListener('click', onPay);
    document.getElementById('walletBtnBack')?.addEventListener('click', () => showStep(1));
    document.getElementById('walletBtnWaiting')?.addEventListener('click', () => {
      if (redirectTimer) clearTimeout(redirectTimer);
    });
    document.getElementById('walletBtnHome')?.addEventListener('click', () => {
      if (redirectTimer) clearTimeout(redirectTimer);
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

  global.AutoHireWallet = { open };
})(window);
