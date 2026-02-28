const nameInput = document.getElementById('name');
const emailInput = document.getElementById('email');
const otpInput = document.getElementById('otp');
const sendLinkBtn = document.getElementById('sendLinkBtn');
const message = document.getElementById('message');

let otpSent = false;
let currentEmail = '';
let currentName = '';

window.addEventListener('DOMContentLoaded', () => {
  if (auth.isAuthenticated()) {
    window.location.href = '/';
  }
});

sendLinkBtn.addEventListener('click', async () => {
  if (!otpSent) {
    const nameValue = nameInput.value.trim();
    const emailValue = emailInput.value.trim();

    if (!nameValue) { showMessage('Please enter your name', 'error'); return; }
    if (!emailValue) { showMessage('Please enter an email address', 'error'); return; }
    if (!isValidEmail(emailValue)) { showMessage('Please enter a valid email address', 'error'); return; }

    sendLinkBtn.disabled = true;
    sendLinkBtn.textContent = 'Sending...';

    try {
      await auth.sendAuthenticationLink(emailValue);
      currentEmail = emailValue;
      currentName = nameValue;
      otpSent = true;

      document.getElementById('nameRow').style.display = 'none';
      document.getElementById('emailRow').style.display = 'none';
      document.getElementById('otpRow').style.display = 'block';
      otpInput.focus();

      showMessage('OTP sent! Check your inbox — if you don\'t see it, check your spam or junk folder.', 'success', false);
      sendLinkBtn.textContent = 'Verify OTP';
    } catch (error) {
      showMessage('Error: ' + error.message, 'error');
    } finally {
      sendLinkBtn.disabled = false;
    }

  } else {
    const otp = otpInput.value.trim();

    if (!otp || !/^\d{6}$/.test(otp)) {
      showMessage('Please enter a valid 6-digit OTP', 'error');
      return;
    }

    sendLinkBtn.disabled = true;
    sendLinkBtn.textContent = 'Verifying...';

    try {
      await auth.verifyOTP(currentEmail, otp, currentName);
      window.location.href = '/';
    } catch (error) {
      showMessage('Invalid OTP. Please try again.', 'error');
      otpInput.value = '';
      otpInput.focus();
      sendLinkBtn.disabled = false;
      sendLinkBtn.textContent = 'Verify OTP';
    }
  }
});

[nameInput, emailInput, otpInput].forEach(el => {
  el.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendLinkBtn.click();
  });
});

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function showMessage(text, type, autoHide = true) {
  message.textContent = text;
  message.className = 'auth-message ' + type;
  message.classList.remove('hidden');
  if (autoHide && type === 'success') {
    setTimeout(() => message.classList.add('hidden'), 5000);
  }
}
