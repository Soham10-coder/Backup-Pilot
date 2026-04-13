document.addEventListener('DOMContentLoaded', function() {
    // Initialize Particles.js background
    if (document.getElementById('particles-js')) {
        particlesJS("particles-js", {
            "particles": {
                "number": { "value": 60, "density": { "enable": true, "value_area": 800 } },
                "color": { "value": "#8b5cf6" },
                "shape": { "type": "circle" },
                "opacity": { "value": 0.4, "random": false },
                "size": { "value": 3, "random": true },
                "line_linked": { "enable": true, "distance": 150, "color": "#8b5cf6", "opacity": 0.3, "width": 1 },
                "move": { "enable": true, "speed": 1.5, "direction": "none", "random": false, "straight": false, "out_mode": "out", "bounce": false }
            },
            "interactivity": {
                "detect_on": "window",
                "events": { 
                    "onhover": { "enable": true, "mode": "grab" }, 
                    "onclick": { "enable": true, "mode": "push" }, 
                    "resize": true 
                },
                "modes": { 
                    "grab": { "distance": 150, "line_linked": { "opacity": 0.6 } }
                }
            },
            "retina_detect": true
        });
    }
});

// Toast notification function
window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'info-circle';
    if(type === 'success') icon = 'check-circle';
    if(type === 'error') icon = 'exclamation-circle';
    if(type === 'warning') icon = 'exclamation-triangle';
    
    toast.innerHTML = `<i class="fa-solid fa-${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    
    // Trigger animation
    requestAnimationFrame(() => {
        setTimeout(() => toast.classList.add('show'), 10);
    });
    
    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300); // Wait for transition
    }, 4000);
}
