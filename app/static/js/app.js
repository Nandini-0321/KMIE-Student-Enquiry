/**
 * KMIE Student Enquiry & Demo Booking Automation
 * Client-Side Enhancements, Micro-Interactions, and Dynamic Goal Filtering
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------------------
    // 1. Dynamic Exam Goal -> Interested Course Filtering
    // -------------------------------------------------------------------------
    const examGoalSelect = document.getElementById('exam_goal');
    const courseSelect = document.getElementById('interested_course');
    const examCoursesDataEl = document.getElementById('exam-courses-data');
    const initialCourseEl = document.getElementById('initial-selected-course');

    let examCoursesMap = {};
    if (examCoursesDataEl) {
        try {
            examCoursesMap = JSON.parse(examCoursesDataEl.textContent.trim());
        } catch (e) {
            console.warn('Could not parse exam-courses-data JSON', e);
        }
    }

    // Fallback if not injected
    if (!examCoursesMap || Object.keys(examCoursesMap).length === 0) {
        examCoursesMap = {
            'NEET': [
                'NEET Long-Term Preparation',
                'NEET Crash Course',
                'NEET Test Series & Rank Booster',
                'Foundation Course (Medical)',
                'Other'
            ],
            'JEE': [
                'JEE Main Preparation',
                'JEE Advanced Preparation',
                'JEE Crash Course',
                'Foundation Course (Engineering)',
                'Other'
            ]
        };
    }

    let initialSelectedCourse = '';
    if (initialCourseEl) {
        try {
            initialSelectedCourse = JSON.parse(initialCourseEl.textContent.trim());
        } catch (e) {
            initialSelectedCourse = '';
        }
    }

    function updateCourseOptions(selectedGoal, preserveValue = '') {
        if (!courseSelect) return;

        // Clear existing options
        courseSelect.innerHTML = '';

        if (!selectedGoal || !examCoursesMap[selectedGoal]) {
            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.disabled = true;
            defaultOpt.selected = true;
            defaultOpt.textContent = '-- Please select Target Exam Goal first --';
            courseSelect.appendChild(defaultOpt);
            courseSelect.disabled = true;
            return;
        }

        courseSelect.disabled = false;
        const placeholderOpt = document.createElement('option');
        placeholderOpt.value = '';
        placeholderOpt.disabled = true;
        placeholderOpt.textContent = `Select ${selectedGoal} Course of Interest`;
        courseSelect.appendChild(placeholderOpt);

        const availableCourses = examCoursesMap[selectedGoal] || [];
        let hasSelected = false;

        availableCourses.forEach(courseName => {
            const opt = document.createElement('option');
            opt.value = courseName;
            opt.textContent = courseName;
            if (preserveValue && preserveValue === courseName) {
                opt.selected = true;
                hasSelected = true;
            }
            courseSelect.appendChild(opt);
        });

        if (!hasSelected) {
            placeholderOpt.selected = true;
        }
    }

    if (examGoalSelect && courseSelect) {
        // Initial setup on page load
        const currentGoal = examGoalSelect.value;
        if (currentGoal) {
            updateCourseOptions(currentGoal, initialSelectedCourse || courseSelect.value);
        } else {
            updateCourseOptions('', '');
        }

        // Change event
        examGoalSelect.addEventListener('change', () => {
            const newGoal = examGoalSelect.value;
            updateCourseOptions(newGoal, '');
            // Highlight course dropdown with smooth focus pulse
            courseSelect.focus();
        });
    }

    // -------------------------------------------------------------------------
    // 2. Indian Phone Number Formatting & Quick Input Sanitization
    // -------------------------------------------------------------------------
    const phoneInput = document.getElementById('phone_number');
    if (phoneInput) {
        phoneInput.addEventListener('input', (e) => {
            let val = e.target.value.trim();
            // Remove +91 or 0091 or leading 0 if entered, keep 10-digit mobile
            val = val.replace(/^(\+91|0091|91)/, '').replace(/\D/g, '');
            if (val.length > 10) {
                val = val.substring(0, 10);
            }
            if (val.length > 5) {
                e.target.value = val.substring(0, 5) + ' ' + val.substring(5);
            } else {
                e.target.value = val;
            }
        });
    }

    const checkStatusPhone = document.getElementById('check-status-phone-input');
    if (checkStatusPhone) {
        checkStatusPhone.addEventListener('input', (e) => {
            let val = e.target.value.trim();
            val = val.replace(/^(\+91|0091|91)/, '').replace(/\D/g, '');
            if (val.length > 10) {
                val = val.substring(0, 10);
            }
            e.target.value = val;
        });
    }

    // -------------------------------------------------------------------------
    // 3. Time Slot Selection Card Highlighting
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
    // 4. Form Submission Spinners & Double-Submit Prevention
    // -------------------------------------------------------------------------
    const enquiryForm = document.getElementById('enquiry-form');
    if (enquiryForm) {
        enquiryForm.addEventListener('submit', (e) => {
            const submitBtn = document.getElementById('btn-submit-enquiry');
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = 'Verifying & Reserving Your Slot...';
                }
                const spinner = submitBtn.querySelector('.spinner');
                if (spinner) {
                    spinner.style.display = 'inline-block';
                }
            }
        });
    }

    const bookingForm = document.getElementById('booking-form');
    if (bookingForm) {
        bookingForm.addEventListener('submit', () => {
            const submitBtn = document.getElementById('btn-confirm-booking');
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = 'Confirming Demo Appointment...';
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // 5. Date Input Past Date Enforcement in Local Time
    // -------------------------------------------------------------------------
    const demoDateInput = document.getElementById('demo_date');
    if (demoDateInput && !demoDateInput.min) {
        const today = new Date().toISOString().split('T')[0];
        demoDateInput.min = today;
    }
});
