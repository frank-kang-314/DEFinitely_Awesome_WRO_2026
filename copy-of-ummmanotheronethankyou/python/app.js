// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
// SPDX-License-Identifier: MPL-2.0

const recentDetectionsElement = document.getElementById('recentDetections');
const feedbackContentElement  = document.getElementById('feedback-content');
const MAX_RECENT_SCANS = 5;
let scans = [];
const socket = io(`http://${window.location.host}`);
let errorContainer = document.getElementById('error-container');

document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();
    initializeConfidenceSlider();
    updateFeedback(null);
    renderDetections();

    const confidencePopoverText = "Minimum confidence score for detected objects.";
    const feedbackPopoverText   = "Current car command based on camera and sensors.";

    document.querySelectorAll('.info-btn.confidence').forEach(img => {
        const popover = img.nextElementSibling;
        img.addEventListener('mouseenter', () => { popover.textContent = confidencePopoverText; popover.style.display = 'block'; });
        img.addEventListener('mouseleave', () => { popover.style.display = 'none'; });
    });
    document.querySelectorAll('.info-btn.feedback').forEach(img => {
        const popover = img.nextElementSibling;
        img.addEventListener('mouseenter', () => { popover.textContent = feedbackPopoverText; popover.style.display = 'block'; });
        img.addEventListener('mouseleave', () => { popover.style.display = 'none'; });
    });

    // Add sensor display elements dynamically
    const rightCol = document.querySelector('.right-column');
    const sensorCard = document.createElement('div');
    sensorCard.className = 'container container-right';
    sensorCard.innerHTML = `
        <h2 class="recent-scans-title">Distance Sensors (cm)</h2>
        <div style="font-family:monospace; font-size:13px; margin-top:8px; line-height:2.2;">
            FRONT: <span id="val-front" style="color:#008184;font-weight:bold;">—</span><br>
            LEFT:  <span id="val-left"  style="color:#008184;font-weight:bold;">—</span><br>
            RIGHT: <span id="val-right" style="color:#008184;font-weight:bold;">—</span>
        </div>`;
    rightCol.insertBefore(sensorCard, rightCol.firstChild);
});

function initSocketIO() {
    socket.on('connect', () => {
        if (errorContainer) { errorContainer.style.display = 'none'; errorContainer.textContent = ''; }
    });
    socket.on('disconnect', () => {
        if (errorContainer) { errorContainer.textContent = 'Connection lost.'; errorContainer.style.display = 'block'; }
    });

    // Original detection event — pillar detections from camera.py
    socket.on('detection', async (message) => {
        printDetection(message);
        renderDetections();
        updateFeedback(message);
    });

    // Sensor readings from Arduino
    socket.on('sensors', (msg) => {
        const f = document.getElementById('val-front');
        const l = document.getElementById('val-left');
        const r = document.getElementById('val-right');
        if (f) f.textContent = msg.front >= 999 ? '>100cm' : msg.front + 'cm';
        if (l) l.textContent = msg.left  >= 999 ? '>100cm' : msg.left  + 'cm';
        if (r) r.textContent = msg.right >= 999 ? '>100cm' : msg.right + 'cm';

        // Colour front red if wall close
        if (f) f.style.color = msg.front < 25 ? '#ff4d4d' : '#008184';
    });

    // Command from Python logic
    socket.on('command', (msg) => {
        updateFeedback({ content: msg.cmd, confidence: 1.0, timestamp: new Date().toISOString() });
    });
}

function updateFeedback(detection) {
    const cmdInfo = {
        "STRAIGHT": { text: "Going straight",       color: "#008184" },
        "LEFT":     { text: "Steering LEFT (RED)",   color: "#ff4d4d" },
        "RIGHT":    { text: "Steering RIGHT (GREEN)", color: "#4dff88" },
    };

    if (detection && cmdInfo[detection.content]) {
        const info = cmdInfo[detection.content];
        feedbackContentElement.innerHTML = `
            <div class="feedback-detection">
                <p style="color:${info.color};font-size:22px;font-weight:bold;">${detection.content}</p>
                <p>${info.text}</p>
            </div>`;
    } else if (detection && detection.content) {
        // Pillar detection fallback
        feedbackContentElement.innerHTML = `
            <div class="feedback-detection">
                <p style="color:#008184;font-size:16px;">${detection.content} detected</p>
            </div>`;
    } else {
        feedbackContentElement.innerHTML = `
            <img src="img/stars.svg" alt="Stars">
            <p class="feedback-text">System response will appear here</p>`;
    }
}

function printDetection(newDetection) {
    scans.unshift(newDetection);
    if (scans.length > MAX_RECENT_SCANS) scans.pop();
}

function renderDetections() {
    recentDetectionsElement.innerHTML = '';
    if (scans.length === 0) {
        recentDetectionsElement.innerHTML = `<div class="no-recent-scans"><img src="./img/no-face.svg">No object detected yet</div>`;
        return;
    }
    scans.forEach((scan) => {
        const row = document.createElement('div');
        row.className = 'scan-container';
        const cellContainer = document.createElement('span');
        cellContainer.className = 'scan-cell-container cell-border';
        const contentText = document.createElement('span');
        contentText.className = 'scan-content';
        const result = Math.floor((scan.confidence || 1) * 1000) / 10;
        contentText.innerHTML = `${result}% - ${scan.content}`;
        const timeText = document.createElement('span');
        timeText.className = 'scan-content-time';
        timeText.textContent = new Date(scan.timestamp).toLocaleString('it-IT').replace(',', ' -');
        cellContainer.appendChild(contentText);
        cellContainer.appendChild(timeText);
        row.appendChild(cellContainer);
        recentDetectionsElement.appendChild(row);
    });
}

function initializeConfidenceSlider() {
    const confidenceSlider  = document.getElementById('confidenceSlider');
    const confidenceInput   = document.getElementById('confidenceInput');
    const confidenceResetButton = document.getElementById('confidenceResetButton');
    confidenceSlider.addEventListener('input', updateConfidenceDisplay);
    confidenceInput.addEventListener('input', handleConfidenceInputChange);
    confidenceInput.addEventListener('blur',  validateConfidenceInput);
    updateConfidenceDisplay();
    confidenceResetButton.addEventListener('click', (e) => {
        if (e.target.classList.contains('reset-icon') || e.target.closest('.reset-icon')) resetConfidence();
    });
}

function handleConfidenceInputChange() {
    const confidenceInput  = document.getElementById('confidenceInput');
    const confidenceSlider = document.getElementById('confidenceSlider');
    let value = parseFloat(confidenceInput.value);
    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;
    confidenceSlider.value = value;
    updateConfidenceDisplay();
}

function validateConfidenceInput() {
    const confidenceInput = document.getElementById('confidenceInput');
    let value = parseFloat(confidenceInput.value);
    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;
    confidenceInput.value = value.toFixed(2);
    handleConfidenceInputChange();
}

function updateConfidenceDisplay() {
    const confidenceSlider       = document.getElementById('confidenceSlider');
    const confidenceInput        = document.getElementById('confidenceInput');
    const confidenceValueDisplay = document.getElementById('confidenceValueDisplay');
    const sliderProgress         = document.getElementById('sliderProgress');
    const value = parseFloat(confidenceSlider.value);
    socket.emit('override_th', value);
    const percentage = (value - confidenceSlider.min) / (confidenceSlider.max - confidenceSlider.min) * 100;
    const displayValue = value.toFixed(2);
    confidenceValueDisplay.textContent = displayValue;
    if (document.activeElement !== confidenceInput) confidenceInput.value = displayValue;
    sliderProgress.style.width = percentage + '%';
    confidenceValueDisplay.style.left = percentage + '%';
}

function resetConfidence() {
    document.getElementById('confidenceSlider').value = '0.5';
    document.getElementById('confidenceInput').value  = '0.50';
    updateConfidenceDisplay();
}