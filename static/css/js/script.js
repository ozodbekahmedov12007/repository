// DOM yuklanganda
document.addEventListener('DOMContentLoaded', function() {
    initPreloader();
    initNavbar();
    initScrollEffects();
    initThemeToggle();
    initBackToTop();
    initSmoothScroll();
    initParticles();

    // Statusni har 3 soniyada yangilash
    setInterval(updateStatus, 3000);

    // Loglarni yuklash
    loadLogs();

    // Statistika
    loadStats();
});

// Preloader
function initPreloader() {
    setTimeout(() => {
        document.getElementById('preloader').classList.add('fade-out');
    }, 1000);
}

// Navbar scroll effect
function initNavbar() {
    const navbar = document.getElementById('navbar');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// Scroll effects
function initScrollEffects() {
    const sections = document.querySelectorAll('section');
    const navLinks = document.querySelectorAll('.nav-link');

    window.addEventListener('scroll', () => {
        let current = '';

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;

            if (window.scrollY >= sectionTop - 200) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    });
}

// Theme toggle
function initThemeToggle() {
    const toggle = document.getElementById('themeToggle');

    toggle.addEventListener('click', () => {
        document.body.classList.toggle('light-theme');

        const icon = toggle.querySelector('i');
        if (document.body.classList.contains('light-theme')) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    });
}

// Back to top button
function initBackToTop() {
    const button = document.getElementById('backToTop');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 500) {
            button.classList.add('show');
        } else {
            button.classList.remove('show');
        }
    });

    button.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Smooth scroll
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();

            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Particles
function initParticles() {
    const particles = document.getElementById('particles');

    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.style.position = 'absolute';
        particle.style.width = Math.random() * 3 + 'px';
        particle.style.height = particle.style.width;
        particle.style.background = `rgba(102, 126, 234, ${Math.random() * 0.5})`;
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.borderRadius = '50%';
        particle.style.animation = `float ${Math.random() * 10 + 5}s infinite ease-in-out`;
        particle.style.animationDelay = Math.random() * 5 + 's';

        particles.appendChild(particle);
    }
}

// Statusni yangilash
function updateStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            document.getElementById('totalVideos').textContent = data.total_videos;
            document.getElementById('queueSize').textContent = data.queue_size;
            document.getElementById('lastRun').textContent = data.last_run || '--:--:--';
            document.getElementById('nextRun').textContent = data.next_run || '--:--:--';
            document.getElementById('currentProcess').textContent = data.current;

            const statusBadge = document.getElementById('statusBadge');
            if (data.current.includes('❌')) {
                statusBadge.className = 'status-badge offline';
            } else if (data.current.includes('✅')) {
                statusBadge.className = 'status-badge success';
            } else {
                statusBadge.className = 'status-badge online';
            }

            // Search progress
            if (data.search_attempt > 0) {
                document.getElementById('searchProgress').style.display = 'block';
                document.getElementById('searchAttempt').textContent =
                    `${data.search_attempt}/10`;
                document.getElementById('searchProgressFill').style.width =
                    (data.search_attempt / 10 * 100) + '%';
                document.getElementById('searchStatus').textContent =
                    data.search_status || 'Qidirilmoqda...';
            } else {
                document.getElementById('searchProgress').style.display = 'none';
            }
        });
}

// Loglarni yuklash
function loadLogs() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            const logsBody = document.getElementById('logsBody');
            logsBody.innerHTML = '';

            data.errors.forEach(error => {
                const logEntry = document.createElement('div');
                logEntry.className = `log-entry error`;
                logEntry.innerHTML = `
                    <span style="color: #888;">[${error.time}]</span>
                    <span style="color: #ff6b6b;">⚠️ ${error.error}</span>
                `;
                logsBody.appendChild(logEntry);
            });

            logsBody.scrollTop = logsBody.scrollHeight;
        });
}

// Statistika yuklash
function loadStats() {
    fetch('/api/stats')
        .then(res => res.json())
        .then(data => {
            document.getElementById('totalVideos').textContent = data.total_videos;
            document.getElementById('queueSize').textContent = data.queue_size;
        });
}

// Botni ishga tushirish
function runBot() {
    showNotification('Bot ishga tushirilmoqda...', 'info');

    document.getElementById('searchProgress').style.display = 'block';
    document.getElementById('searchQueries').innerHTML = '';

    fetch('/force-run', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showNotification('Bot ishga tushdi! Video qidirilmoqda...', 'success');
            }
        });
}

// Video qidirishni qayta boshlash
function retrySearch() {
    document.getElementById('noVideoModal').classList.remove('show');
    document.getElementById('searchQueries').innerHTML = '';

    fetch('/api/retry-search', { method: 'POST' })
        .then(() => {
            runBot();
        });
}

// Fallback video ishlatish
function useFallback() {
    document.getElementById('noVideoModal').classList.remove('show');

    fetch('/api/use-fallback', { method: 'POST' })
        .then(() => {
            showNotification('Fallback video ishlatilmoqda...', 'warning');
            runBot();
        });
}

// Sozlamalarni o'zgartirish
function changeSettings() {
    document.getElementById('noVideoModal').classList.remove('show');
    document.getElementById('settings').scrollIntoView({ behavior: 'smooth' });
}

// Jarayonni bekor qilish
function cancelProcess() {
    document.getElementById('noVideoModal').classList.remove('show');
    document.getElementById('searchProgress').style.display = 'none';

    fetch('/api/cancel-search', { method: 'POST' })
        .then(() => {
            showNotification('Jarayon bekor qilindi', 'error');
        });
}

// Loglarni tozalash
function clearLogs() {
    if (confirm('Loglarni tozalashni xohlaysizmi?')) {
        fetch('/clear-logs', { method: 'POST' })
            .then(() => {
                document.getElementById('logsBody').innerHTML = '';
                showNotification('Loglar tozalandi', 'success');
            });
    }
}

// Loglarni yuklab olish
function downloadLogs() {
    window.location.href = '/download-logs';
}

// Vaqtni saqlash
function saveSchedule() {
    const time1 = document.getElementById('time1').value;
    const time2 = document.getElementById('time2').value;

    showNotification(`Vaqt saqlandi: ${time1} va ${time2}`, 'success');
}

// Botni start
function startBot() {
    showNotification('Bot ishga tushirildi', 'success');
}

// Botni pause
function pauseBot() {
    showNotification('Bot vaqtincha to\'xtatildi', 'warning');
}

// Botni restart
function restartBot() {
    showNotification('Bot qayta ishga tushirilmoqda...', 'info');
    setTimeout(() => {
        showNotification('Bot qayta ishga tushdi', 'success');
    }, 2000);
}

// Schedule modal
function openSchedule() {
    alert('Vaqt sozlamalari dashboard bo\'limida');
}

// Notification
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification show ${type}`;

    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// Mobile menu
document.getElementById('mobileMenu') ? .addEventListener('click', () => {
    const navMenu = document.getElementById('navMenu');
    navMenu.style.display = navMenu.style.display === 'flex' ? 'none' : 'flex';
});

// Filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        const filter = this.dataset.filter;
        const logs = document.querySelectorAll('.log-entry');

        logs.forEach(log => {
            if (filter === 'all' || log.classList.contains(filter)) {
                log.style.display = 'block';
            } else {
                log.style.display = 'none';
            }
        });
    });
});