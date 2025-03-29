document.addEventListener('DOMContentLoaded', () => {
    // Function to force a repaint
    function forceRepaint() {
        document.body.style.display = 'none';
        document.body.offsetHeight; // Trigger reflow
        document.body.style.display = 'block';
    }

    // Function to apply text color to all elements manually
    function applyTextColor(color) {
        document.documentElement.style.setProperty('--text-color', color);
        // Fallback: Directly apply to elements
        document.querySelectorAll('.nav-tabs .nav-link, body, .card, .table th, .table td, .form-control, .form-select').forEach(element => {
            element.style.color = color;
        });
        forceRepaint();
    }

    // Theme Color
    const themeColorPicker = document.getElementById('themeColor');
    if (themeColorPicker) {
        themeColorPicker.addEventListener('input', () => {
            const themeColor = themeColorPicker.value;
            document.documentElement.style.setProperty('--primary-color', themeColor);
            localStorage.setItem('themeColor', themeColor);
            forceRepaint();
        });

        const savedThemeColor = localStorage.getItem('themeColor') || '#2c3e50';
        document.documentElement.style.setProperty('--primary-color', savedThemeColor);
        themeColorPicker.value = savedThemeColor;
    }

    // Font Color
    const fontColorPicker = document.getElementById('fontColor');
    if (fontColorPicker) {
        fontColorPicker.addEventListener('input', () => {
            const fontColor = fontColorPicker.value;
            console.log('Font color changed to:', fontColor); // Debug log
            applyTextColor(fontColor); // Use the new function
            localStorage.setItem('fontColor', fontColor);
        });

        const savedFontColor = localStorage.getItem('fontColor') || '#212529';
        applyTextColor(savedFontColor);
        fontColorPicker.value = savedFontColor;
    }

    // Font Size
    const fontSizeSlider = document.getElementById('fontSize');
    if (fontSizeSlider) {
        fontSizeSlider.addEventListener('input', () => {
            const fontSize = fontSizeSlider.value + 'px';
            document.documentElement.style.setProperty('--font-size', fontSize);
            localStorage.setItem('fontSize', fontSizeSlider.value);
            forceRepaint();
        });

        const savedFontSize = localStorage.getItem('fontSize') || '16';
        document.documentElement.style.setProperty('--font-size', savedFontSize + 'px');
        fontSizeSlider.value = savedFontSize;
    }

    // Theme Toggle
    const toggleModeBtn = document.getElementById('toggleMode');
    if (toggleModeBtn) {
        toggleModeBtn.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
            const isDarkMode = document.body.classList.contains('dark-mode');
            document.getElementById('modeIcon').innerHTML = isDarkMode ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
            localStorage.setItem('themeMode', isDarkMode ? 'dark' : 'light');
            forceRepaint();
        });

        const savedThemeMode = localStorage.getItem('themeMode');
        if (savedThemeMode === 'dark') {
            document.body.classList.add('dark-mode');
            document.getElementById('modeIcon').innerHTML = '<i class="fas fa-sun"></i>';
        }
    }
});