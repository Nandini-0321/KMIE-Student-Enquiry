/**
 * KMIE Student Enquiry & Demo Booking Automation
 * Client-Side Enhancements & Form Micro-Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------------------
    // 1. Time Slot Selection Card Highlighting
    // -------------------------------------------------------------------------
    const slotCards = document.querySelectorAll('.slot-card');
    slotCards.forEach(card => {
        const radio = card.querySelector('.slot-radio');
        card.addEventListener('click', () => {
            slotCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            if (radio) {
                radio.checked = true;
            }
        });
    });

    // -------------------------------------------------------------------------
    // 2. Prevent Double Submissions & Display Button Spinners
    // -------------------------------------------------------------------------
    const enquiryForm = document.getElementById('enquiry-form');
    if (enquiryForm) {
        enquiryForm.addEventListener('submit', (e) => {
            const submitBtn = document.getElementById('btn-submit-enquiry');
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = 'Validating & Processing Enquiry...';
                }
            }
        });
    }

    const bookingForm = document.getElementById('booking-form');
    if (bookingForm) {
        bookingForm.addEventListener('submit', (e) => {
            const submitBtn = document.getElementById('btn-confirm-booking');
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = 'Reserving Demo Slot...';
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // 3. Date Input Past Date Enforcement in Local Time
    // -------------------------------------------------------------------------
    const demoDateInput = document.getElementById('demo_date');
    if (demoDateInput && !demoDateInput.min) {
        const today = new Date().toISOString().split('T')[0];
        demoDateInput.min = today;
    }
});
