const pageNames = {
    home: 'Tổng quan',
    import: 'Import POI',
    delete: 'Xóa POI',
    address: 'Tạo Address',
    category: 'Mapping Category',
    compare: 'So sánh & Lọc Excel',
    geocode: 'Geocode Map4D',
    route: 'Route Simulation'
};

function navigate(el, page) {
    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    if (el) el.classList.add('active');

    // Update breadcrumb
    document.getElementById('currentPageName').textContent = pageNames[page] || page;

    // Show/hide welcome screen
    document.getElementById('welcomeScreen').style.display = page === 'home' ? 'flex' : 'none';

    // Show/hide tool iframes
    document.querySelectorAll('.tool-frame').forEach(f => f.classList.remove('active'));
    if (page !== 'home') {
        const frame = document.getElementById(`frame-${page}`);
        if (frame) frame.classList.add('active');
    }
}
