// ANPR data
let plateData = [];

let whitelistEntries = [];
let selectedEntry = null;

// DOM Elements
const darkModeToggle = document.getElementById('darkModeToggle');
const whitelistButton = document.getElementById('whitelistButton');
const whitelistModal = document.getElementById('whitelistModal');
const confirmDialog = document.getElementById('confirmDialog');
const whitelistForm = document.getElementById('whitelistForm');
const closeButtons = document.querySelectorAll('.close-button');
const confirmButton = document.getElementById('confirmButton');
const cancelButton = document.getElementById('cancelButton');

fetch('/get_data')
  .then(response => response.json())
  .then(data => {
    plateData = data;
    console.log(plateData); 
    renderANPRTable();
  })
  .catch(error => console.error('Error fetching data:', error));

function getConfidenceClass(score) {
  if (score >= 80) return 'confidence-high';
  if (score >= 60) return 'confidence-medium';
  return 'confidence-low';
}

function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// Initialize tables
function initializeTables() {
    renderANPRTable();
    renderWhitelistTable();
}

// Add these DOM elements at the top with other elements
const imageOverlay = document.getElementById('imageOverlay');
const enlargedImage = document.getElementById('enlargedImage');

// Add this function to handle image clicks
function handleImageClick(imageSrc) {
  enlargedImage.src = imageSrc;
  console.log('Original src:', imageSrc);
  imageOverlay.classList.add('active');
}

// Update renderANPRTable to add click handlers
function renderANPRTable() {
    const tbody = document.querySelector('#anprTable tbody');

    if (!tbody) {
        console.error("Table body element not found!");
        return;
    }

    tbody.innerHTML = plateData.slice().reverse().map(record => {
        // Normalize the image path by replacing backslashes with forward slashes
        const normalizedImagePath = record.image.replace(/\\/g, '/');
        return `
        <tr>
            <td>${record.id}</td>
            <td>${record.plateNo}</td>
            <td>${record.type}</td>
            <td>
                <span class="confidence-badge ${getConfidenceClass(record.confidenceScore)}">
                ${record.confidenceScore}%
                </span>
            </td>
            <td><img src="${normalizedImagePath}" alt="${record.plateNo}" onclick="handleImageClick('${normalizedImagePath}')"></td>
            <td>${record.detectionTime}</td>
            <td><a href="https://www.carinfo.app/rc-details/${record.plateNo}">Link</a></td>
        </tr>
    `;
    }).join('');
}

// Add click handler for overlay background to close when clicking outside
imageOverlay.addEventListener('click', (e) => {
  if (e.target === imageOverlay) {
    imageOverlay.classList.remove('active');
  }
});

// Render whitelist table
function renderWhitelistTable() {
    const tbody = document.querySelector('#whitelistTable tbody');
    tbody.innerHTML = whitelistEntries.map(entry => `
        <tr>
            <td>${entry.name}</td>
            <td>${entry.plateNo}</td>
            <td>${entry.type}</td>
            <td>
                <button onclick="handleRemoveWhitelist(${entry.id})" class="icon-button text-red-600">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                </button>
            </td>
        </tr>
    `).join('');
}

// Dark mode toggle
darkModeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    const icon = darkModeToggle.querySelector('svg');
    if (document.body.classList.contains('dark')) {
        icon.innerHTML = '<circle cx="12" cy="12" r="5"/><path d="M12 1v2"/><path d="M12 21v2"/><path d="M4.22 4.22l1.42 1.42"/><path d="M18.36 18.36l1.42 1.42"/><path d="M1 12h2"/><path d="M21 12h2"/><path d="M4.22 19.78l1.42-1.42"/><path d="M18.36 5.64l1.42-1.42"/>';
    } else {
        icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    }
});

// Whitelist modal
whitelistButton.addEventListener('click', () => {
    whitelistModal.classList.add('active');
});

closeButtons.forEach(button => {
    button.addEventListener('click', () => {
        whitelistModal.classList.remove('active');
        confirmDialog.classList.remove('active');
    });
});

// Add to whitelist
whitelistForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const newEntry = {
        name: document.getElementById('name').value,
        plateNo: document.getElementById('plateNo').value,
        type: document.getElementById('type').value
    };

    console.log('New whitelist entry:', newEntry);  // To debug

    fetch('/add_to_whitelist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEntry)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            fetchWhitelistData();
            whitelistForm.reset();
            whitelistModal.classList.remove('active');
        } else {
            console.error('Error adding to whitelist:', data.error);
        }
    })
    .catch(error => console.error('Error:', error));
});

function fetchWhitelistData() {
    fetch('/get_whitelist')
    .then(response => response.json())
    .then(data => {
        whitelistEntries = data;
        renderWhitelistTable();
    })
    .catch(error => console.error('Error fetching whitelist data:', error));
}

fetchWhitelistData();

// Remove from whitelist
window.handleRemoveWhitelist = (id) => {
    selectedEntry = whitelistEntries.find(entry => entry.id === id);
    confirmDialog.classList.add('active');
};

confirmButton.addEventListener('click', () => {
    if (selectedEntry) {
        whitelistEntries = whitelistEntries.filter(entry => entry.id !== selectedEntry.id);
        renderWhitelistTable();
        selectedEntry = null;
    }
    confirmDialog.classList.remove('active');
});

cancelButton.addEventListener('click', () => {
    confirmDialog.classList.remove('active');
    selectedEntry = null;
});

// Initialize the application
initializeTables();