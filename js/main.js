// ==================== GLOBAL BACKDROP CLEANUP ====================
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
        backdrop.remove();
    });
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
});
document.addEventListener('hidden.bs.modal', function () {
    document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
        backdrop.remove();
    });
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
});

// ==================== LOGIN FUNCTION ====================
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
        if (!document.querySelector('.modal.show')) {
            backdrop.remove();
            document.body.classList.remove('modal-open');
        }
    });
});

function login() {
    const form = document.getElementById('loginForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    const email = document.getElementById('emailInp').value.trim();
    const password = document.getElementById('passwordInp').value;
    const remember = document.getElementById('rememberCheck').checked;

    // Clear previous errors
    document.getElementById('emailInp').classList.remove('input-error-glow');
    document.getElementById('invalidEmail').classList.remove('error-message-shimmer');
    document.getElementById('invalidEmail').innerText = '';
    document.getElementById('passwordInp').classList.remove('input-error-glow');
    document.getElementById('invalidPassword').classList.remove('error-message-shimmer');
    document.getElementById('invalidPassword').innerText = '';

    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: password, remember: remember })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (data.isAdmin === 'admin') {
                window.location.href = '/admin-index';
            } else {
                window.location.href = '/index';
            }
        } else {
            if (data.error === 'email') {
                document.getElementById('emailInp').value = '';
                document.getElementById('emailInp').classList.add('input-error-glow');
                const errDiv = document.getElementById('invalidEmail');
                errDiv.innerText = data.message;
                errDiv.classList.add('error-message-shimmer');
            } else {
                document.getElementById('passwordInp').value = '';
                document.getElementById('passwordInp').classList.add('input-error-glow');
                const errDiv = document.getElementById('invalidPassword');
                errDiv.innerText = data.message;
                errDiv.classList.add('error-message-shimmer');
            }
        }
    })
    .catch(err => console.error('Error:', err));
}

// ==================== REGISTER FUNCTION ====================
function register() {
    const form = document.getElementById('registerForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    const name = document.getElementById('nameInp').value.trim();
    const email = document.getElementById('emailInp').value.trim();
    const newPassword = document.getElementById('newPasswordInp').value;
    const confirmPassword = document.getElementById('confirmPasswordInp').value;
    const role = document.getElementById('role')?.value || 'user';
    const balanceDeposit = parseFloat(document.getElementById('balanceDeposit').value) || 0;

    if (email.toLowerCase().endsWith('@auto-hire.com')) {
        const emailError = document.getElementById('emailInpError');
        if (emailError) {
            emailError.innerText = 'Registration with @auto-hire.com emails is not allowed.';
            emailError.classList.remove('d-none');
        }
        document.getElementById('emailInp').value = '';
        return;
    }

    if (newPassword !== confirmPassword) {
        document.getElementById('confirmPasswordInp').classList.add("border", "border-danger");
        document.getElementById('invalidConfirmPassword').innerText = 'Passwords do not match';
        return;
    }
    document.getElementById('confirmPasswordInp').classList.remove("border", "border-danger");
    document.getElementById('invalidConfirmPassword').innerText = '';

    const profileImageURL = document.getElementById('profileImageInp')?.value.trim() || '';
    let userData = {
        name: name,
        email: email,
        password: newPassword,
        role: role,
        profile_image_url: profileImageURL,
        birth_date: document.getElementById('birthDateInp')?.value || null,
        balance_deposit: balanceDeposit
    };

    if (role === 'user') {
        userData.license_number = document.getElementById('licenseNumberInp')?.value.trim() || '';
        userData.license_expiry = document.getElementById('licenseExpiryInp')?.value || '';
    }

    fetch('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.href = '/verify';
        } else {
            alert(data.message || 'Registration failed.');
            const emailError = document.getElementById('emailInpError');
            if (emailError) {
                emailError.innerText = data.message || 'Registration error';
                emailError.classList.remove('d-none');
            }
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Network error. Please try again later.');
    });
}

// ==================== OTP VERIFICATION ====================
function verifyOTP() {
    const form = document.getElementById('verifyForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    const otpCode = document.getElementById('otpInput').value.trim();
    fetch('/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ otp: otpCode })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            document.getElementById('successMessage').classList.remove('d-none');
            setTimeout(() => window.location.href = '/login', 2000);
        } else {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.innerText = data.message || 'Invalid OTP. Please try again.';
            errorDiv.classList.remove('d-none');
        }
    })
    .catch(err => {
        console.error('Error:', err);
        document.getElementById('errorMessage').innerText = 'An error occurred. Please try again.';
        document.getElementById('errorMessage').classList.remove('d-none');
    });
}

// ==================== RESEND OTP ====================
function resendOTP() {
    const btn = document.getElementById('resendBtn');
    btn.disabled = true;
    fetch('/resend-otp', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('A new code has been sent to your email!');
            startResendTimer();
        } else {
            alert(data.message || 'Error resending code.');
            btn.disabled = false;
        }
    })
    .catch(err => {
        console.error('Error:', err);
        btn.disabled = false;
    });
}

function startResendTimer() {
    let timeLeft = 30;
    const timerText = document.getElementById('timerText');
    const resendBtn = document.getElementById('resendBtn');
    const secondsSpan = document.getElementById('seconds');
    resendBtn.classList.add('d-none');
    timerText.classList.remove('d-none');
    const countdown = setInterval(() => {
        timeLeft--;
        secondsSpan.textContent = timeLeft;
        if (timeLeft <= 0) {
            clearInterval(countdown);
            timerText.classList.add('d-none');
            resendBtn.classList.remove('d-none');
            resendBtn.disabled = false;
        }
    }, 1000);
}

// ==================== REAL‑TIME UNIQUENESS CHECK ====================
let uniquenessTimers = {};
function checkFieldUniqueness(fieldId, fieldName) {
    const input = document.getElementById(fieldId);
    if (!input) return;
    const value = input.value.trim();
    if (!value) {
        clearFieldError(input);
        return;
    }
    if (uniquenessTimers[fieldId]) clearTimeout(uniquenessTimers[fieldId]);
    uniquenessTimers[fieldId] = setTimeout(() => {
        fetch('/check-unique', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: fieldName, value: value })
        })
        .then(res => res.json())
        .then(data => {
            if (data.exists) {
                input.classList.add('is-invalid', 'input-error-glow');
                const errorSpan = document.getElementById(fieldId + 'Error');
                if (errorSpan) {
                    errorSpan.innerText = `This ${fieldName.replace('_', ' ')} is already in use!`;
                    errorSpan.classList.remove('d-none');
                    errorSpan.classList.add('error-message-shimmer');
                }
                input.value = '';
                setTimeout(() => clearFieldError(input), 3000);
            } else {
                clearFieldError(input);
            }
        })
        .catch(err => console.error('Uniqueness check failed:', err));
    }, 500);
}

function clearFieldError(input) {
    input.classList.remove('is-invalid', 'input-error-glow');
    const errorSpan = document.getElementById(input.id + 'Error');
    if (errorSpan) {
        errorSpan.innerText = '';
        errorSpan.classList.add('d-none');
        errorSpan.classList.remove('error-message-shimmer');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('registerForm')) return;
    const nameInput = document.getElementById('nameInp');
    if (nameInput) {
        nameInput.addEventListener('input', () => checkFieldUniqueness('nameInp', 'name'));
        nameInput.addEventListener('blur', () => checkFieldUniqueness('nameInp', 'name'));
    }
    const emailInput = document.getElementById('emailInp');
    if (emailInput) {
        emailInput.addEventListener('input', () => checkFieldUniqueness('emailInp', 'email'));
        emailInput.addEventListener('blur', () => checkFieldUniqueness('emailInp', 'email'));
    }
    const licenseInput = document.getElementById('licenseNumberInp');
    if (licenseInput) {
        licenseInput.addEventListener('input', () => checkFieldUniqueness('licenseNumberInp', 'license_number'));
        licenseInput.addEventListener('blur', () => checkFieldUniqueness('licenseNumberInp', 'license_number'));
    }
});

// ==================== BOOKING FORM VALIDATION ====================
document.addEventListener('DOMContentLoaded', function() {
    const bookingForm = document.getElementById('bookingForm');
    if (bookingForm) {
        const pickupDateInput = document.getElementById('pickup_date');
        const returnDateInput = document.getElementById('return_date');
        const pickupTimeInput = document.getElementById('pickup_time');
        const returnTimeInput = document.getElementById('return_time');
        const todayStr = new Date().toISOString().slice(0, 10);

        function createErrorSpan(inputElement, message) {
            const span = document.createElement('span');
            span.className = 'text-danger small d-none';
            span.style.color = '#ff4d4d';
            span.innerText = message;
            const parentCol = inputElement.closest('.col-md-6, .position-relative');
            if (parentCol) parentCol.appendChild(span);
            else inputElement.parentNode.appendChild(span);
            return span;
        }

        const ERROR_MSG = 'Please enter a correct date.';
        let pickupErrorSpan = document.getElementById('pickupDateError');
        if (!pickupErrorSpan) {
            pickupErrorSpan = createErrorSpan(pickupDateInput, ERROR_MSG);
            pickupErrorSpan.id = 'pickupDateError';
        }
        let returnErrorSpan = document.getElementById('returnDateError');
        if (!returnErrorSpan) {
            returnErrorSpan = createErrorSpan(returnDateInput, ERROR_MSG);
            returnErrorSpan.id = 'returnDateError';
        }

        function validateDateNotPast(input, errorSpan) {
            const val = input.value;
            if (!val) {
                errorSpan.classList.add('d-none');
                return true;
            }
            if (val < todayStr) {
                input.value = '';
                errorSpan.classList.remove('d-none');
                errorSpan.innerText = ERROR_MSG;
                return false;
            } else {
                errorSpan.classList.add('d-none');
                return true;
            }
        }

        function validateReturnAfterPickup() {
            const pickupVal = pickupDateInput.value;
            const returnVal = returnDateInput.value;
            if (!pickupVal || !returnVal) {
                returnErrorSpan.classList.add('d-none');
                return true;
            }
            if (returnVal < pickupVal) {
                returnDateInput.value = '';
                returnErrorSpan.classList.remove('d-none');
                returnErrorSpan.innerText = ERROR_MSG;
                return false;
            } else {
                returnErrorSpan.classList.add('d-none');
                return true;
            }
        }

        function getMinPickupTime() {
            const now = new Date();
            now.setMinutes(now.getMinutes() + 30);
            let hours = now.getHours();
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12;
            if (hours === 0) hours = 12;
            return `${hours}:${minutes} ${ampm}`;
        }

        function validatePickupTime() {
            if (!pickupTimeInput || !pickupDateInput) return true;
            const pickupDateVal = pickupDateInput.value;
            const pickupTimeVal = pickupTimeInput.value; 
            const errorDiv = document.getElementById('pickupTimeError');
            if (!pickupDateVal || !pickupTimeVal) {
                if (errorDiv) errorDiv.classList.add('d-none');
                pickupTimeInput.setCustomValidity('');
                return true;
            }
            const today = new Date().toISOString().slice(0, 10);
            if (pickupDateVal === today) {
                const minTime24 = (() => {
                    const now = new Date();
                    now.setMinutes(now.getMinutes() + 30);
                    const hh = String(now.getHours()).padStart(2, '0');
                    const mm = String(now.getMinutes()).padStart(2, '0');
                    return `${hh}:${mm}`;
                })();
                if (pickupTimeVal < minTime24) {
                    pickupTimeInput.value = '';
                    if (errorDiv) {
                        errorDiv.textContent = `Pickup time must be at least 30 minutes from now (${getMinPickupTime()}).`;
                        errorDiv.classList.remove('d-none');
                    }
                    pickupTimeInput.setCustomValidity('Invalid pickup time.');
                    pickupTimeInput.reportValidity();
                    return false;
                } else {
                    pickupTimeInput.setCustomValidity('');
                    if (errorDiv) errorDiv.classList.add('d-none');
                }
            } else {
                pickupTimeInput.setCustomValidity('');
                if (errorDiv) errorDiv.classList.add('d-none');
            }
            return true;
        }

        if (pickupTimeInput) {
            pickupTimeInput.addEventListener('input', validatePickupTime);
            pickupTimeInput.addEventListener('change', validatePickupTime);
        }
        if (pickupDateInput) {
            pickupDateInput.addEventListener('change', function() {
                validateDateNotPast(this, pickupErrorSpan);
                if (returnDateInput.value) validateReturnAfterPickup();
                validatePickupTime();
            });
        }
        if (returnDateInput) {
            returnDateInput.addEventListener('change', function() {
                validateDateNotPast(this, returnErrorSpan);
                validateReturnAfterPickup();
            });
        }

        bookingForm.addEventListener('submit', function(e) {
            let valid = true;
            if (!validateDateNotPast(pickupDateInput, pickupErrorSpan)) valid = false;
            if (!validateDateNotPast(returnDateInput, returnErrorSpan)) valid = false;
            if (!validateReturnAfterPickup()) valid = false;
            if (!validatePickupTime()) valid = false;
            const pickupDate = pickupDateInput?.value;
            const pickupTime = pickupTimeInput?.value;
            const returnDate = returnDateInput?.value;
            const returnTime = returnTimeInput?.value;
            const startStr = pickupDate && pickupTime ? `${pickupDate}T${pickupTime}` : null;
            const endStr = returnDate && returnTime ? `${returnDate}T${returnTime}` : null;
            if (!startStr || !endStr) {
                valid = false;
            } else {
                const start = new Date(startStr);
                const end = new Date(endStr);
                const diffMs = end - start;
                const totalMinutes = Math.ceil(diffMs / (1000 * 60));
                const errorEl = document.getElementById('bookingError');
                if (totalMinutes < 60) {
                    if (errorEl) {
                        errorEl.classList.remove('d-none');
                        errorEl.innerText = 'Minimum rental duration is 1 hour.';
                    } else {
                        alert('Minimum rental duration is 1 hour.');
                    }
                    valid = false;
                } else {
                    if (errorEl) errorEl.classList.add('d-none');
                }
            }
            if (!valid) {
                e.preventDefault();
                return false;
            }
        });
    }

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) { e.preventDefault(); login(); });
    }
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) { e.preventDefault(); register(); });
    }
    const verifyForm = document.getElementById('verifyForm');
    if (verifyForm) {
        verifyForm.addEventListener('submit', function(e) { e.preventDefault(); verifyOTP(); });
    }
    if (document.getElementById('timerText')) startResendTimer();
});

// ==================== MAP PICKER ====================
(function() {
    let currentFieldId = null;
    let map = null;
    let marker = null;
    let mapInitialized = false;
    const mapModalEl = document.getElementById('mapPickerModal');
    const saveBtn = document.getElementById('saveMapLocationBtn');
    const fallbackTextEl = document.getElementById('mapFallbackText');

    function setupLeafletIcons() {
        if (typeof L !== 'undefined') {
            delete L.Icon.Default.prototype._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
                iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
                shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
            });
        }
    }

    async function fetchDepot() {
        try {
            const res = await fetch('/api/depot');
            if (res.ok) return await res.json();
        } catch (e) { console.warn(e); }
        return { lat: 31.5204, lng: 74.3587, name: 'AutoHire Depot (Lahore)' };
    }

    async function reverseGeocode(lat, lng) {
        try {
            const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`;
            const res = await fetch(url, { headers: { 'Accept': 'application/json', 'User-Agent': 'AutoHire-Demo/1.0' } });
            if (!res.ok) throw new Error('Nominatim error');
            return await res.json();
        } catch (e) { console.warn(e); return null; }
    }

    async function updateMarkerAddress(latlng) {
        if (!marker) return;
        const res = await reverseGeocode(latlng.lat, latlng.lng);
        if (res && res.display_name) {
            marker.formatted_address = res.display_name;
            if (fallbackTextEl) fallbackTextEl.innerText = '📍 ' + res.display_name;
        } else {
            marker.formatted_address = `${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}`;
            if (fallbackTextEl) fallbackTextEl.innerText = '📍 ' + marker.formatted_address;
        }
    }

    function placeMarkerLatLng(latlng) {
        if (!map) return;
        if (marker) map.removeLayer(marker);
        marker = L.marker([latlng.lat, latlng.lng], { draggable: true }).addTo(map);
        map.setView([latlng.lat, latlng.lng], 14);
        marker.on('dragend', function() {
            const pos = marker.getLatLng();
            updateMarkerAddress({ lat: pos.lat, lng: pos.lng });
        });
        updateMarkerAddress(latlng);
    }

    function initializeMap(initialView) {
        const mapCanvas = document.getElementById('mapCanvas');
        if (!mapCanvas) return;
        if (map && mapInitialized) {
            map.invalidateSize();
            map.setView([initialView.lat, initialView.lng], 12);
            return;
        }
        mapCanvas.innerHTML = '';
        const fallbackDiv = document.createElement('div');
        fallbackDiv.id = 'mapFallbackText';
        fallbackDiv.className = 'text-center text-muted p-3';
        fallbackDiv.innerText = 'Loading map...';
        mapCanvas.appendChild(fallbackDiv);
        const newFallbackTextEl = document.getElementById('mapFallbackText');
        setupLeafletIcons();
        try {
            map = L.map('mapCanvas', { zoomControl: true, maxZoom: 19 }).setView([initialView.lat, initialView.lng], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map);
            map.on('click', function(e) { placeMarkerLatLng({ lat: e.latlng.lat, lng: e.latlng.lng }); });
            if (newFallbackTextEl) newFallbackTextEl.innerText = 'Click on the map to select a location';
            mapInitialized = true;
        } catch (e) {
            console.error(e);
            if (newFallbackTextEl) newFallbackTextEl.innerText = 'Map failed to load.';
        }
    }

    function openMapPicker(fieldId) {
        currentFieldId = fieldId;
        if (typeof L === 'undefined') { alert('Map library loading...'); return; }
        if (typeof bootstrap === 'undefined') { alert('Bootstrap not loaded.'); return; }
        try {
            const modal = new bootstrap.Modal(mapModalEl);
            modal.show();
            mapModalEl.addEventListener('shown.bs.modal', async function onModalShown() {
                mapModalEl.removeEventListener('shown.bs.modal', onModalShown);
                const depot = await fetchDepot();
                setTimeout(() => {
                    initializeMap({ lat: depot.lat, lng: depot.lng });
                    const input = document.getElementById(currentFieldId);
                    if (input && input.value) {
                        const val = input.value.trim();
                        if (val) {
                            const coordMatch = val.match(/(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)/);
                            if (coordMatch) {
                                const lat = parseFloat(coordMatch[1]), lng = parseFloat(coordMatch[2]);
                                setTimeout(() => placeMarkerLatLng({ lat, lng }), 500);
                            } else {
                                try {
                                    const saved = localStorage.getItem(currentFieldId + '_location');
                                    if (saved) {
                                        const loc = JSON.parse(saved);
                                        if (loc.lat && loc.lng) setTimeout(() => placeMarkerLatLng({ lat: loc.lat, lng: loc.lng }), 500);
                                    }
                                } catch(e) {}
                            }
                        }
                    }
                }, 200);
            }, { once: true });
        } catch(e) { alert('Error opening map.'); }
    // After computing totalMinutes
/*if (totalMinutes < 120) {   // 2 hours = 120 minutes
    document.getElementById('modalReserveBtn').style.display = 'none';
    const warning = document.createElement('div');
    warning.className = 'alert alert-warning mt-2';
    warning.innerText = 'Minimum rental is 2 hours. Please adjust your dates.';
    document.getElementById('modalBookingSummary').appendChild(warning);
} else {
    document.getElementById('modalReserveBtn').style.display = 'block';
}*/
    }

    function attachMapButtonListeners() {
        const pickupBtn = document.getElementById('pickup_map_btn');
        const returnBtn = document.getElementById('return_map_btn');
        if (pickupBtn) {
            const newPickupBtn = pickupBtn.cloneNode(true);
            pickupBtn.parentNode.replaceChild(newPickupBtn, pickupBtn);
            newPickupBtn.addEventListener('click', function(e) { e.preventDefault(); openMapPicker('pickup_location'); });
        }
        if (returnBtn) {
            const newReturnBtn = returnBtn.cloneNode(true);
            returnBtn.parentNode.replaceChild(newReturnBtn, returnBtn);
            newReturnBtn.addEventListener('click', function(e) { e.preventDefault(); openMapPicker('return_location'); });
        }
        if (saveBtn) {
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
            newSaveBtn.addEventListener('click', function() {
                if (!currentFieldId) return;
                const input = document.getElementById(currentFieldId);
                if (input && marker && typeof marker.getLatLng === 'function') {
                    const p = marker.getLatLng();
                    const name = marker.formatted_address || `${p.lat.toFixed(6)}, ${p.lng.toFixed(6)}`;
                    input.value = name;
                    localStorage.setItem(currentFieldId + '_location', JSON.stringify({ lat: p.lat, lng: p.lng, name }));
                }
                const modal = bootstrap.Modal.getInstance(mapModalEl);
                if (modal) modal.hide();
                currentFieldId = null;
            });
        }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attachMapButtonListeners);
    else attachMapButtonListeners();
})();

// ==================== OPEN CAR DETAILS MODAL ====================
function openCarModal(car, start, end, pickupLocParam, returnLocParam) {
    document.getElementById('modalImg').src = car.img_url;
    document.getElementById('modalModel').innerText = car.model;
    document.getElementById('modalType').innerText = car.category ? car.category.replace('Car', '') : (car.class ? car.class.name.replace('Car', '') : '');
    document.getElementById('modalVin').innerText = car.vin;
    document.getElementById('modalColour').innerText = car.colour;
    document.getElementById('modalSeats').innerText = car.seating_capacity;
    document.getElementById('modalRate').innerText = `${car.base_rate} PKR`;
    
    let extra = '';
    if (car.category === "EconomyCar" || car.class?.name === "EconomyCar") {
        extra = `<p class="mb-1 text-muted small">Fuel Efficiency:</p><p class="fw-semibold">${car.fuel_efficiency || 'N/A'} km/l</p>`;
    } else if (car.category === "LuxuryCar" || car.class?.name === "LuxuryCar") {
        extra = `<p class="mb-1 text-muted small">Chauffeur Available:</p><p class="fw-semibold">${car.chauffeur_available ? 'Yes' : 'No'}</p>`;
    } else if (car.category === "CommercialCar" || car.class?.name === "CommercialCar") {
        extra = `<p class="mb-1 text-muted small">Cargo Capacity:</p><p class="fw-semibold">${car.cargo_capacity || 'N/A'} kg</p>`;
    }
    document.getElementById('modalExtraSpec').innerHTML = extra;
    
    const featuresContainer = document.getElementById('modalFeatures');
    featuresContainer.innerHTML = '';
    if (car.features) {
        for (const [feature, value] of Object.entries(car.features)) {
            const badge = document.createElement('span');
            badge.className = `badge ${value ? 'bg-success' : 'bg-secondary'} me-1`;
            badge.innerText = feature.replace('_', ' ').toUpperCase();
            featuresContainer.appendChild(badge);
        }
    }
    
    try {
        const parseToDate = (s) => {
            if (!s) return null;
            if (s.includes('T')) return new Date(s);
            return new Date(s + 'T00:00:00');
        };
        const startDt = parseToDate(start);
        const endDt = parseToDate(end);
        if (startDt && endDt && endDt > startDt) {
            const diffMs = endDt - startDt;
            const totalMinutes = Math.ceil(diffMs / (1000 * 60));
            const days = Math.floor(totalMinutes / (60 * 24));
            const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
            const minutes = totalMinutes % 60;
            document.getElementById('modalDuration').innerText = `${days} day(s) ${hours} hour(s) ${minutes} minute(s)`;
            
            const perHour = Number(car.base_rate) / 24;
            const perMinute = perHour / 60;
            const priceDays = days * Number(car.base_rate);
            const priceHours = hours * perHour;
            const priceMinutes = minutes * perMinute;
            const totalPrice = priceDays + priceHours + priceMinutes;
            const parts = [];
            if (priceDays) parts.push(`${days} day(s) × ${Number(car.base_rate).toFixed(2)} PKR = ${priceDays.toFixed(2)} PKR`);
            if (hours) parts.push(`${hours} hour(s) × ${perHour.toFixed(2)} PKR = ${priceHours.toFixed(2)} PKR`);
            if (minutes) parts.push(`${minutes} minute(s) × ${perMinute.toFixed(4)} PKR = ${priceMinutes.toFixed(2)} PKR`);
            document.getElementById('modalPriceBreakdown').innerHTML = parts.join('<br>') || `0 hour(s) × ${perHour.toFixed(2)} PKR = 0.00 PKR`;
            document.getElementById('modalTotalPrice').innerText = `${totalPrice.toFixed(2)} PKR`;
            
            const hoursParam = Math.ceil(totalMinutes / 60);
            const reserveBtn = document.getElementById('modalReserveBtn');
            const urlParams = new URLSearchParams(window.location.search);
            const sTime = urlParams.get('start_time') || '';
            const eTime = urlParams.get('end_time') || '';

            if (reserveBtn) {
                reserveBtn.href = `/reserve/${car.vin}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&pickup_loc=${encodeURIComponent(pickupLocParam || '')}&return_loc=${encodeURIComponent(returnLocParam || '')}&start_time=${encodeURIComponent(sTime)}&end_time=${encodeURIComponent(eTime)}&hours=${hoursParam}&total_minutes=${totalMinutes}&minutes=${minutes}&total_price=${encodeURIComponent(totalPrice.toFixed(2))}`;
            }
        } else {
            const reserveBtn = document.getElementById('modalReserveBtn');
            if (reserveBtn) reserveBtn.href = `/reserve/${car.vin}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
        }
    } catch (e) { console.error(e); }
    
    const modal = new bootstrap.Modal(document.getElementById('carDetailsModal'));
    modal.show();
}

// ==================== ADMIN FLEET FUNCTIONS ====================
function toggleCarFields(type) {
    const economyEl = document.getElementById("economy-fields");
    const luxuryEl = document.getElementById("luxury-fields");
    const commercialEl = document.getElementById("commercial-fields");
    if (economyEl) economyEl.classList.add("d-none");
    if (luxuryEl) luxuryEl.classList.add("d-none");
    if (commercialEl) commercialEl.classList.add("d-none");
    
    if (type === "EconomyCar" || type === "Economy") { if (economyEl) economyEl.classList.remove("d-none"); }
    else if (type === "LuxuryCar" || type === "Luxury") { if (luxuryEl) luxuryEl.classList.remove("d-none"); }
    else if (type === "CommercialCar" || type === "Commercial") { if (commercialEl) commercialEl.classList.remove("d-none"); }
}

function handleEditButtonClick(button) {
    try {
        const car = JSON.parse(button.dataset.car);
        openEditCarModal(car);
    } catch (err) { alert('Error loading car data.'); }
}

function openEditCarModal(car) {
    const get = (obj, ...keys) => { for (const k of keys) { if (obj && k in obj) return obj[k]; } return undefined; };
    const vin = get(car, 'vin');
    const model = get(car, 'model');
    const base_rate = get(car, 'base_rate', 'baseRate');
    const img_url = get(car, 'img_url', 'imgUrl');
    const seating_capacity = get(car, 'seating_capacity', 'seatingCapacity');
    const colour = get(car, 'colour', 'color');
    const car_type = get(car, 'car_type', 'category');
    const features = get(car, 'features', {});
    
    const setIf = (id, value) => { const el = document.getElementById(id); if (el && value !== undefined) el.value = value; };
    setIf('vin', vin);
    setIf('model', model);
    setIf('base_rate', base_rate);
    setIf('img_url', img_url);
    setIf('seating_capacity', seating_capacity);
    setIf('colour', colour);
    setIf('car_type', car_type);
    
    const vinEl = document.getElementById('vin'); if (vinEl) vinEl.disabled = true;
    if (features && typeof features === 'object') {
        for (const [feature, value] of Object.entries(features)) {
            const cb = document.getElementById(feature);
            if (cb) cb.checked = value === true || value === 'true' || value === '1';
        }
    }
    toggleCarFields(car_type);
    if (car_type === 'EconomyCar') setIf('fuel_efficiency', get(car, 'fuel_efficiency'));
    else if (car_type === 'LuxuryCar') {
        const chauff = get(car, 'chauffeur_available');
        const chauffEl = document.getElementById('chauffeur_available');
        if (chauffEl) chauffEl.value = chauff ? (chauff === true ? '1' : '0') : '0';
    } else if (car_type === 'CommercialCar') setIf('cargo_capacity', get(car, 'cargo_capacity'));
    
    const form = document.querySelector('#carForm');
    if (form) form.action = `/admin/edit_car/${vin}`;
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    if (submitBtn) {
        submitBtn.innerHTML = '<i class="bi bi-pencil-fill"></i> Update Car';
        submitBtn.classList.remove('btn-success');
        submitBtn.classList.add('btn-warning');
    }
    const titleEl = document.getElementById('carModalLabel');
    if (titleEl) titleEl.innerText = 'Edit Car';
    
    const modal = new bootstrap.Modal(document.getElementById('addCarModal'));
    modal.show();
}

function openAddCarModal() {
    document.getElementById("carForm").reset();
    const vinInput = document.getElementById("vin");
    if (vinInput) { vinInput.disabled = false; vinInput.value = ""; }
    const features = ["air_conditioning", "bluetooth", "gps", "usb_ports", "sunroof", "rear_camera"];
    features.forEach(f => { const cb = document.getElementById(f); if (cb) cb.checked = false; });
    toggleCarFields("");
    const fuelEff = document.getElementById("fuel_efficiency"); if (fuelEff) fuelEff.value = "";
    const chauff = document.getElementById("chauffeur_available"); if (chauff) chauff.value = "0";
    const cargo = document.getElementById("cargo_capacity"); if (cargo) cargo.value = "";
    const form = document.getElementById("carForm");
    if (form) form.action = "/admin/add_car";
    const titleEl = document.getElementById('carModalLabel');
    if (titleEl) titleEl.innerText = "Add New Car";
    const modal = new bootstrap.Modal(document.getElementById('addCarModal'));
    modal.show();
}

// ==================== LIVE PASSWORD VALIDATION ====================
function setupPasswordValidation() {
    const newPwd = document.getElementById('newPasswordInp');
    const confirmPwd = document.getElementById('confirmPasswordInp');
    const errPwd = document.getElementById('invalidPassword');
    const errConfirm = document.getElementById('invalidConfirmPassword');
    
    if (newPwd) {
        newPwd.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            if (errPwd) { errPwd.innerText = ''; errPwd.classList.add('d-none'); }
            if (confirmPwd && confirmPwd.value) confirmPwd.dispatchEvent(new Event('input'));
        });
    }
    if (confirmPwd) {
        confirmPwd.addEventListener('input', function() {
            const password = newPwd ? newPwd.value : '';
            if (this.value !== password) {
                this.classList.add('is-invalid');
                if (errConfirm) { errConfirm.innerText = 'Passwords do not match'; errConfirm.classList.remove('d-none'); }
            } else {
                this.classList.remove('is-invalid');
                if (errConfirm) { errConfirm.innerText = ''; errConfirm.classList.add('d-none'); }
            }
        });
    }

    const resetNew = document.getElementById('new_password');
    const resetConfirm = document.getElementById('confirm_password');
    const resetErrNew = document.getElementById('resetNewPasswordError');
    const resetErrConfirm = document.getElementById('resetConfirmPasswordError');
    if (resetNew) {
        resetNew.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            if (resetErrNew) { resetErrNew.innerText = ''; resetErrNew.classList.add('d-none'); }
            if (resetConfirm && resetConfirm.value) resetConfirm.dispatchEvent(new Event('input'));
        });
    }
    if (resetConfirm) {
        resetConfirm.addEventListener('input', function() {
            const password = resetNew ? resetNew.value : '';
            if (this.value !== password) {
                this.classList.add('is-invalid');
                if (resetErrConfirm) { resetErrConfirm.innerText = 'Passwords do not match'; resetErrConfirm.classList.remove('d-none'); }
            } else {
                this.classList.remove('is-invalid');
                if (resetErrConfirm) { resetErrConfirm.innerText = ''; resetErrConfirm.classList.add('d-none'); }
            }
        });
    }
    
    const loginPwd = document.getElementById('passwordInp');
    if (loginPwd) {
        loginPwd.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            const err = document.getElementById('invalidPassword');
            if (err) { err.innerText = ''; err.classList.add('d-none'); }
        });
    }
}
document.addEventListener('DOMContentLoaded', setupPasswordValidation);

// ==================== USER NOTIFICATION POPUPS ====================
document.addEventListener('DOMContentLoaded', function () {
    const profileImg = document.querySelector('.rounded-circle');
    if (!profileImg) return;
    
    async function loadAndShowNotifications() {
        try {
            const res = await fetch('/api/notifications');
            const notifications = await res.json();
            if (!notifications.length) return;
            
            for (const notif of notifications) {
                if (notif.type === 'admin_approve') await showApprovalModal(notif.message);
                else if (notif.type === 'admin_reject') await showRejectionModal(notif.message);
                else if (notif.type === 'admin_cancelled') await showAdminCancelledModal(notif.message);
                else if (notif.type === 'admin_edit') await showAdminEditModal(notif.message); 
            }
            
            const ids = notifications.map(n => n.id);
            await fetch('/api/notifications/mark-read', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ ids }) 
            });
        } catch (e) { console.error(e); }
    }

    function extractReservationId(message) { 
        const match = message.match(/reservation ([\w-]+)/); 
        return match ? match[1] : null; 
    }

    function showApprovalModal(message) { 
        return new Promise((resolve) => {
            const rid = extractReservationId(message);
            const modalId = 'approvalModal' + Date.now();
            const html = `<div class="modal fade" id="${modalId}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-success"><div class="modal-header bg-success text-white"><h5 class="modal-title">🎉 Reservation Approved!</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>${message}</p></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><a href="/track/${rid}" class="btn btn-success">Go to Tracking Page</a></div></div></div></div>`;
            document.body.insertAdjacentHTML('beforeend', html);
            const modalEl = document.getElementById(modalId);
            const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
            modalEl.addEventListener('hidden.bs.modal', function () { modalEl.remove(); resolve(); });
            modal.show();
        }); 
    }

    function showRejectionModal(message) { 
        return new Promise((resolve) => {
            const modalId = 'rejectModal' + Date.now();
            const html = `<div class="modal fade" id="${modalId}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-danger"><div class="modal-header bg-danger text-white"><h5 class="modal-title">Reservation Rejected</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>${message}</p><p>Please try again later or contact support.</p></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">OK</button></div></div></div></div>`;
            document.body.insertAdjacentHTML('beforeend', html);
            const modalEl = document.getElementById(modalId);
            const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
            modalEl.addEventListener('hidden.bs.modal', function () { modalEl.remove(); resolve(); });
            modal.show();
        }); 
    }

    function showAdminCancelledModal(message) { 
        return new Promise((resolve) => {
            const modalId = 'adminCancelModal' + Date.now();
            const html = `<div class="modal fade" id="${modalId}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-warning"><div class="modal-header bg-warning"><h5 class="modal-title">⚠️ Reservation Cancelled by Admin</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>${message}</p></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">OK</button></div></div></div></div>`;
            document.body.insertAdjacentHTML('beforeend', html);
            const modalEl = document.getElementById(modalId);
            const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
            modalEl.addEventListener('hidden.bs.modal', function () { modalEl.remove(); resolve(); });
            modal.show();
        }); 
    }

    function showAdminEditModal(message) { 
        return new Promise((resolve) => {
            const modalId = 'adminEditModal' + Date.now();
            const html = `<div class="modal fade" id="${modalId}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-info"><div class="modal-header bg-info text-white"><h5 class="modal-title">ℹ️ Reservation Updated by Admin</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>${message}</p></div><div class="modal-footer"><button type="button" class="btn btn-primary" data-bs-dismiss="modal">Acknowledge</button></div></div></div></div>`;
            document.body.insertAdjacentHTML('beforeend', html);
            const modalEl = document.getElementById(modalId);
            const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
            modalEl.addEventListener('hidden.bs.modal', function () { modalEl.remove(); resolve(); });
            modal.show();
        }); 
    }

    loadAndShowNotifications();
});

// Attach confirmation to any element with class="needs-confirm"
document.addEventListener('DOMContentLoaded', function() {
    const confirmButtons = document.querySelectorAll('.sohaib-zohaib');
    confirmButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            const message = this.getAttribute('sohaib-zohaib-msg') || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                e.preventDefault();   // stop default action (navigation, submit)
                e.stopPropagation();
                return false;
            }
            // if OK, the default action continues
        });
    });
});