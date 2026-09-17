// CodeSentinel Frontend Application JS

const PRESETS = {
    vulnerable_auth: `import os
import sqlite3

# Hardcoded Secret & Injection Vulnerability Demo
API_KEY_SECRET = "sk_live_99283719283719283719"

def authenticate_user(username, password_input):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # CRITICAL SECURITY RISK: SQL Injection via string formatting
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password_input}'"
    cursor.execute(query)
    
    user = cursor.fetchone()
    
    # Unsafe eval execution
    if user and eval("user[1] == 'admin'"):
        print("Admin access granted")
        
    return user`,

    nested_loops: `import time
import requests

class DataProcessor:
    def process_records(self, user_ids, items):
        results = []
        
        # PERFORMANCE RISK: O(N^2) Nested loop with N+1 Network Call
        for u_id in user_ids:
            for item in items:
                # Synchronous network call inside nested loop
                response = requests.get(f"https://api.internal.com/check/{u_id}/{item}")
                if response.status_code == 200:
                    results.append(response.json())
                    
        # Unclosed file handle resource leak
        f = open("audit.log", "a")
        f.write(f"Processed {len(results)} items")
        
        return results`,

    pep8_issues: `from os import *

class userProcessorClass:
    def ProcessDataAndCalculateUserTotals(self, UserDataList):
        TotalCount = 0
        try:
            for item in UserDataList:
                TotalCount += item
        except:
            pass
        return TotalCount`,

    clean_code: `import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class UserAccount:
    user_id: int
    username: str
    is_active: bool = True

def calculate_active_user_count(users: List[UserAccount]) -> int:
    """
    Calculates total active users in list efficiently.
    """
    return sum(1 for u in users if u.is_active)`
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadPreset('vulnerable_auth');
    fetchDashboardStats();
    loadHistory();
});

function loadPreset(presetKey) {
    const editor = document.getElementById('code-editor');
    if (PRESETS[presetKey]) {
        editor.value = PRESETS[presetKey];
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));

    if (tabName === 'simulator') {
        document.querySelector('.tab-btn:nth-child(1)').classList.add('active');
        document.getElementById('tab-simulator').classList.remove('hidden');
    } else {
        document.querySelector('.tab-btn:nth-child(2)').classList.add('active');
        document.getElementById('tab-history').classList.remove('hidden');
        loadHistory();
    }
}

async function fetchDashboardStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('stat-total-prs').innerText = data.total_prs_reviewed;
        document.getElementById('stat-security-count').innerText = data.security_findings;
        document.getElementById('stat-perf-count').innerText = data.performance_findings;
        document.getElementById('stat-style-count').innerText = data.style_findings;
        document.getElementById('stat-avg-score').innerHTML = `${data.avg_severity_score} <small>/ 100</small>`;
    } catch (e) {
        console.error("Failed to load dashboard stats", e);
    }
}

async function runPRSimulation() {
    const repo = document.getElementById('sim-repo').value || "acme/web-service";
    const prNum = parseInt(document.getElementById('sim-pr').value || "104");
    const filename = document.getElementById('sim-filename').value || "app/auth.py";
    const diffContent = document.getElementById('code-editor').value;

    if (!diffContent.trim()) {
        alert("Please paste code diff content to analyze.");
        return;
    }

    // Toggle UI state
    document.getElementById('results-empty').classList.add('hidden');
    document.getElementById('results-content').classList.add('hidden');
    document.getElementById('loading-spinner').classList.remove('hidden');

    const stepText = document.getElementById('agent-step-text');
    stepText.innerText = "Step 1/3: Running AST Code Chunker & SecurityAgent...";

    try {
        const payload = {
            repo_full_name: repo,
            pr_number: prNum,
            pr_title: `Simulation: Update ${filename}`,
            author: "agent_tester",
            filename: filename,
            diff_content: diffContent
        };

        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            throw new Error(`Server returned status ${res.status}`);
        }

        const data = await res.json();

        // Render Results
        renderReviewResults(data);
        fetchDashboardStats();
    } catch (err) {
        alert("Simulation failed: " + err.message);
        document.getElementById('loading-spinner').classList.add('hidden');
        document.getElementById('results-empty').classList.remove('hidden');
    }
}

function renderReviewResults(data) {
    document.getElementById('loading-spinner').classList.add('hidden');
    document.getElementById('results-content').classList.remove('hidden');

    // Score Badge
    const badge = document.getElementById('results-score-badge');
    badge.classList.remove('hidden');
    badge.innerText = `Severity Score: ${data.severity_score}/100`;

    // Summary Card
    const summaryCard = document.getElementById('review-summary-card');
    summaryCard.innerHTML = formatMarkdown(data.summary);

    // Findings List
    const list = document.getElementById('findings-list');
    list.innerHTML = "";

    if (!data.findings || data.findings.length === 0) {
        list.innerHTML = `
            <div class="finding-card LOW">
                <div class="finding-header">
                    <span class="finding-title">✨ All Checks Passed</span>
                    <span class="severity-tag LOW">PASS</span>
                </div>
                <p class="finding-desc">No security vulnerabilities, performance bottlenecks, or PEP8 style issues found in this chunk.</p>
            </div>
        `;
        return;
    }

    data.findings.forEach(f => {
        const card = document.createElement('div');
        card.className = `finding-card ${f.severity}`;
        
        let suggestionHtml = '';
        if (f.suggestion) {
            suggestionHtml = `<div class="suggestion-box">${escapeHtml(f.suggestion)}</div>`;
        }

        card.innerHTML = `
            <div class="finding-header">
                <span class="finding-title">[${f.agent_type}] ${escapeHtml(f.issue_title)} (Line ${f.line_number})</span>
                <span class="severity-tag ${f.severity}">${f.severity}</span>
            </div>
            <div class="finding-desc">${escapeHtml(f.description)}</div>
            ${suggestionHtml}
        `;
        list.appendChild(card);
    });
}

async function loadHistory() {
    try {
        const res = await fetch('/api/reviews');
        if (!res.ok) return;
        const prs = await res.json();

        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = "";

        if (prs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center">No review sessions recorded yet. Run a simulation above!</td></tr>`;
            return;
        }

        prs.forEach(pr => {
            pr.reviews.forEach(review => {
                const tr = document.createElement('tr');
                const dateStr = new Date(review.created_at).toLocaleString();

                tr.innerHTML = `
                    <td><code>#${review.id}</code></td>
                    <td><strong>${escapeHtml(pr.repo_full_name)}</strong> #${pr.pr_number}</td>
                    <td>${escapeHtml(pr.title)}</td>
                    <td><code>${escapeHtml(pr.author)}</code></td>
                    <td><span class="badge-score">${review.severity_score}/100</span></td>
                    <td>🔒 ${review.security_count} | ⚡ ${review.performance_count} | 🎨 ${review.style_count}</td>
                    <td><small>${dateStr}</small></td>
                `;
                tbody.appendChild(tr);
            });
        });
    } catch (e) {
        console.error("Failed to load review history", e);
    }
}

function formatMarkdown(text) {
    if (!text) return "";
    return text
        .replace(/## (.*)/g, '<h2>$1</h2>')
        .replace(/### (.*)/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/- (.*)/g, '<li>$1</li>');
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
