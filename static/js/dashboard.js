// Initialize tooltips
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', e => {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = element.getAttribute('data-tooltip');
            
            document.body.appendChild(tooltip);
            
            const rect = element.getBoundingClientRect();
            tooltip.style.left = `${rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
            tooltip.style.top = `${rect.bottom + 10}px`;
            
            requestAnimationFrame(() => tooltip.classList.add('visible'));
        });
        
        element.addEventListener('mouseleave', () => {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });
    });
}

// Calendar Event Rendering
function renderCalendarEvents(events) {
    const container = document.getElementById('weeklyCalendar');
    if (!container) return;

    container.innerHTML = '';
    
    events.forEach(event => {
        const eventEl = document.createElement('div');
        eventEl.className = `calendar-event event-type-${event.type}`;
        eventEl.setAttribute('data-tooltip', `${event.time} • ${event.coach} • ${event.studentCount} students`);
        
        eventEl.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-bold">${event.title}</h4>
                    <p class="text-sm text-gray-400">${event.time}</p>
                </div>
                <div class="text-sm">
                    <span class="mr-2">${event.studentCount} 👥</span>
                    <i class="fas fa-chevron-right"></i>
                </div>
            </div>
        `;
        
        container.appendChild(eventEl);
    });
}

// Attendance List Rendering
function renderAttendanceList(classes) {
    const container = document.getElementById('attendanceList');
    if (!container) return;

    container.innerHTML = '';
    
    classes.forEach(classItem => {
        const itemEl = document.createElement('div');
        itemEl.className = 'attendance-item';
        
        itemEl.innerHTML = `
            <div class="flex-1">
                <h4 class="font-bold">${classItem.name}</h4>
                <p class="text-sm text-gray-400">${classItem.time}</p>
            </div>
            <div class="flex items-center space-x-4">
                <div class="text-right">
                    <span class="text-sm text-gray-400">Checked-in</span>
                    <p class="font-bold">${classItem.checkedIn}/${classItem.total}</p>
                </div>
                <button class="p-2 bg-bg-hover rounded-lg hover:bg-bg-active transition-colors"
                        onclick="window.location.href='/attendance/${classItem.id}'">
                    <i class="fas fa-qrcode"></i>
                </button>
            </div>
        `;
        
        container.appendChild(itemEl);
    });
}

// Updates Panel Rendering
function renderUpdates(updates) {
    const container = document.getElementById('updatesContainer');
    if (!container) return;

    container.innerHTML = '';
    
    updates.forEach(update => {
        const updateEl = document.createElement('div');
        updateEl.className = 'update-item';
        
        updateEl.innerHTML = `
            <div class="flex items-start space-x-3">
                <div class="w-8 h-8 rounded-full bg-bg-hover flex items-center justify-center flex-shrink-0">
                    <i class="fas ${update.type === 'announcement' ? 'fa-bullhorn' : 'fa-calendar-xmark'} 
                       text-${update.type === 'announcement' ? 'accent-secondary' : 'accent-primary'}"></i>
                </div>
                <div class="flex-1">
                    <p class="mb-1">${update.message}</p>
                    <p class="text-sm text-gray-400">${update.time}</p>
                </div>
            </div>
        `;
        
        container.appendChild(updateEl);
    });
}

// Chart Rendering
function initCharts() {
    // Attendance Trend Chart
    const attendanceCtx = document.querySelector('.attendance-trend-chart');
    if (attendanceCtx) {
        // Initialize your preferred charting library here
        // Example: Chart.js, ApexCharts, etc.
    }

    // Revenue Chart
    const revenueCtx = document.querySelector('.revenue-chart');
    if (revenueCtx) {
        // Initialize your preferred charting library here
    }
}

// Profile Dropdown
function initProfileDropdown() {
    const dropdown = document.getElementById('profileDropdown');
    if (!dropdown) return;

    const button = dropdown.querySelector('button');
    const menu = document.createElement('div');
    menu.className = 'absolute right-0 mt-2 w-48 bg-bg-card rounded-lg shadow-lg py-2 hidden';
    menu.innerHTML = `
        <a href="/profile" class="block px-4 py-2 hover:bg-bg-hover">Profile</a>
        <a href="/settings" class="block px-4 py-2 hover:bg-bg-hover">Settings</a>
        <hr class="my-2 border-bg-tertiary">
        <a href="/logout" class="block px-4 py-2 hover:bg-bg-hover text-status-error">Logout</a>
    `;
    
    dropdown.appendChild(menu);
    
    button.addEventListener('click', () => {
        menu.classList.toggle('hidden');
    });
    
    document.addEventListener('click', e => {
        if (!dropdown.contains(e.target)) {
            menu.classList.add('hidden');
        }
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initTooltips();
    initProfileDropdown();
    initCharts();
    
    // Example data - replace with your actual data fetching
    renderCalendarEvents([
        {
            title: 'Mathematics Class',
            time: '9:00 AM',
            type: 'class',
            coach: 'John Doe',
            studentCount: 15
        },
        // Add more events...
    ]);
    
    renderAttendanceList([
        {
            id: 1,
            name: 'Physics Class',
            time: '10:00 AM',
            checkedIn: 12,
            total: 15
        },
        // Add more classes...
    ]);
    
    renderUpdates([
        {
            type: 'announcement',
            message: 'New schedule for next week posted',
            time: '2 hours ago'
        },
        // Add more updates...
    ]);
});
