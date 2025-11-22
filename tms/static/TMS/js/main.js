// static/TMS/js/main.js
document.addEventListener("DOMContentLoaded", function () {
    console.log("TMS Groups Website Loaded - 2025 Edition");

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Auto-hide navbar on scroll down (mobile friendly)
    let prevScrollpos = window.pageYOffset;
    window.onscroll = function () {
        let currentScrollPos = window.pageYOffset;
        if (prevScrollpos > currentScrollPos) {
            document.querySelector(".navbar").style.top = "0";
        } else {
            document.querySelector(".navbar").style.top = "-100px";
        }
        prevScrollpos = currentScrollPos;
    }

    // Floating WhatsApp Pulse Animation (already in CSS, but enhance)
    const waButton = document.querySelector('.fixed-wa a');
    if (waButton) {
        waButton.addEventListener('mouseenter', () => {
            waButton.style.transform = 'scale(1.2)';
        });
        waButton.addEventListener('mouseleave', () => {
            waButton.style.transform = 'scale(1)';
        });
    }

    // Lazy load images (optional performance boost)
    const images = document.querySelectorAll('img');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src || img.src;
                img.classList.add('loaded');
                observer.unobserve(img);
            }
        });
    });

    images.forEach(img => {
        if (img.getAttribute('loading') !== 'eager') {
            img.setAttribute('loading', 'lazy');
        }
    });

    // Auto-play video when in view (for product detail page)
    const videos = document.querySelectorAll('video');
    const videoObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.play();
            } else {
                entry.target.pause();
            }
        });
    }, { threshold: 0.5 });

    videos.forEach(video => {
        videoObserver.observe(video);
    });

    // Add loading animation to WhatsApp buttons
    document.querySelectorAll('a[href*="wa.me"]').forEach(btn => {
        btn.addEventListener('click', function () {
            this.innerHTML = '<i class="fab fa-whatsapp"></i> Opening WhatsApp...';
            this.style.opacity = '0.8';
        });
    });

    // Toast notification (optional future use)
    window.showToast = function (message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed`;
        toast.style.top = '20px';
        toast.style.right = '20px';
        toast.style.zIndex = '9999';
        toast.style.minWidth = '300px';
        toast.innerHTML = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    };

    // Show success message after lead submit (if redirected back)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('lead') === 'success') {
        setTimeout(() => {
            showToast('Thank You! Your enquiry has been sent. We will contact you soon!', 'success');
        }, 1000);
    }
});