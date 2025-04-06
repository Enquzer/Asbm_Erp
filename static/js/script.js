$(document).ready(function() {
    function forceRepaint() {
        document.body.style.display = 'none';
        document.body.offsetHeight;
        document.body.style.display = 'block';
    }

    function applyTextColor(color) {
        document.documentElement.style.setProperty('--text-color', color);
        document.documentElement.style.setProperty('--body-color', color);
        $('.nav-tabs .nav-link, body, .card, .table th, .table td, .form-control, .form-select, .nav-link, .navbar-text, .dropdown-item').css('color', color);
        forceRepaint();
    }

    // Theme Color Picker
    const $themeColorPicker = $('#themeColor');
    if ($themeColorPicker.length) {
        $themeColorPicker.on('input', function() {
            const themeColor = $(this).val();
            document.documentElement.style.setProperty('--primary-color', themeColor);
            document.documentElement.style.setProperty('--navbar-bg', themeColor);
            localStorage.setItem('themeColor', themeColor);
            forceRepaint();
        });
        const savedThemeColor = localStorage.getItem('themeColor') || '#c0392b';
        document.documentElement.style.setProperty('--primary-color', savedThemeColor);
        document.documentElement.style.setProperty('--navbar-bg', savedThemeColor);
        $themeColorPicker.val(savedThemeColor);
    }

    // Font Color Picker
    const $fontColorPicker = $('#fontColor');
    if ($fontColorPicker.length) {
        $fontColorPicker.on('input', function() {
            const fontColor = $(this).val();
            applyTextColor(fontColor);
            localStorage.setItem('fontColor', fontColor);
        });
        const savedFontColor = localStorage.getItem('fontColor') || '#212529';
        applyTextColor(savedFontColor);
        $fontColorPicker.val(savedFontColor);
    }

    // Font Size Slider
    const $fontSizeSlider = $('#fontSize');
    if ($fontSizeSlider.length) {
        $fontSizeSlider.on('input', function() {
            const fontSize = $(this).val() + 'px';
            document.documentElement.style.setProperty('--font-size', fontSize);
            document.documentElement.style.setProperty('--bs-body-font-size', fontSize);
            localStorage.setItem('fontSize', $(this).val());
            forceRepaint();
        });
        const savedFontSize = localStorage.getItem('fontSize') || '16';
        document.documentElement.style.setProperty('--font-size', savedFontSize + 'px');
        document.documentElement.style.setProperty('--bs-body-font-size', savedFontSize + 'px');
        $fontSizeSlider.val(savedFontSize);
    }

    // Dark Mode Toggle
    const $toggleModeBtn = $('#toggleMode');
    if ($toggleModeBtn.length) {
        $toggleModeBtn.on('click', function() {
            $('body').toggleClass('dark-mode');
            const isDarkMode = $('body').hasClass('dark-mode');
            $('#modeIcon').html(isDarkMode ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>');
            localStorage.setItem('themeMode', isDarkMode ? 'dark' : 'light');
            if (!isDarkMode) {
                // Reset to light mode colors
                const savedThemeColor = localStorage.getItem('themeColor') || '#c0392b';
                document.documentElement.style.setProperty('--navbar-bg', savedThemeColor);
                document.documentElement.style.setProperty('--body-bg', '#f8f9fa');
                document.documentElement.style.setProperty('--footer-bg', '#2c3e50');
                document.documentElement.style.setProperty('--link-color', '#212529');
                document.documentElement.style.setProperty('--link-hover', '#d4d4d4');
                document.documentElement.style.setProperty('--card-bg', '#ffffff');
                document.documentElement.style.setProperty('--card-hover-bg', '#f1f1f1');
                document.documentElement.style.setProperty('--chat-bg', '#ffffff');
                document.documentElement.style.setProperty('--chat-hover-bg', '#f1f1f1');
            }
            forceRepaint();
        });
        const savedThemeMode = localStorage.getItem('themeMode');
        if (savedThemeMode === 'dark') {
            $('body').addClass('dark-mode');
            $('#modeIcon').html('<i class="fas fa-sun"></i>');
        } else {
            $('#modeIcon').html('<i class="fas fa-moon"></i>');
        }
    }

    // HR Module Form Submissions
    const forms = [
        { id: 'addEmployeeForm', multipart: true },
        { id: 'addOvertimeForm', multipart: false },
        { id: 'addAttendanceForm', multipart: false },
        { id: 'addLeaveForm', multipart: false },
        { id: 'addLetterForm', multipart: false },
        { id: 'addContractForm', multipart: false },
        { id: 'addPositionForm', multipart: false }
    ];

    forms.forEach(({ id, multipart }) => {
        $(document).on('submit', `#${id}`, function(e) {
            e.preventDefault();
            const $form = $(this);
            const formData = multipart ? new FormData(this) : $form.serialize();
            console.log(`Submitting ${id}:`, multipart ? [...formData.entries()] : formData);
            $.ajax({
                url: '/hr/',
                method: 'POST',
                data: formData,
                processData: multipart ? false : true,
                contentType: multipart ? false : 'application/x-www-form-urlencoded',
                dataType: 'json'
            })
            .done(data => {
                alert(data.message);
                if (data.status === 'success') {
                    location.reload();
                } else if (data.errors) {
                    console.error('Errors:', data.errors);
                }
            })
            .fail(error => {
                console.error('Error:', error);
                alert(`An error occurred while submitting ${id.replace('Form', '')}.`);
            });
        });
    });

    $(document).on('submit', '[id^="modifyEmployeeForm"]', function(e) {
        e.preventDefault();
        const $form = $(this);
        console.log('Submitting Modify Employee:', $form.serialize());
        $.ajax({
            url: '/hr/',
            method: 'POST',
            data: $form.serialize(),
            contentType: 'application/x-www-form-urlencoded',
            dataType: 'json'
        })
        .done(data => {
            alert(data.message);
            if (data.status === 'success') {
                location.reload();
            }
        })
        .fail(error => {
            console.error('Error:', error);
            alert('An error occurred while updating the employee.');
        });
    });

    window.deleteEmployee = function(employeeId) {
        if (confirm('Are you sure you want to delete this employee?')) {
            $.ajax({
                url: '/hr/',
                method: 'POST',
                data: {
                    action: 'delete_employee',
                    employee_id: employeeId,
                    csrf_token: $('input[name="csrf_token"]').val()
                },
                contentType: 'application/x-www-form-urlencoded',
                dataType: 'json'
            })
            .done(data => {
                alert(data.message);
                if (data.status === 'success') {
                    location.reload();
                }
            })
            .fail(error => {
                console.error('Error:', error);
                alert('An error occurred while deleting the employee.');
            });
        }
    };

    window.updateEmployeeDropdown = function(dutyStationId, selectId) {
        const $employeeSelect = $(`#${selectId}`);
        $employeeSelect.html('<option value="">Select Employee</option>');
        if (dutyStationId) {
            $.getJSON(`/hr/employees_by_duty_station?duty_station_id=${dutyStationId}`, data => {
                data.employees.forEach(emp => {
                    $employeeSelect.append(`<option value="${emp.id}">${emp.name}</option>`);
                });
            }).fail(error => console.error('Error fetching employees:', error));
        }
    };
});