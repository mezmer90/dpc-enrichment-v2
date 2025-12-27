/**
 * User-Friendly JSON Formatter
 *
 * Formats JSON data into a collapsible, readable structure with:
 * - Nested objects as collapsible sections
 * - Arrays shown with item counts
 * - URLs made clickable
 * - Booleans shown as Yes/No
 * - Empty values hidden
 */

function formatPracticeData(data) {
    let html = '<div style="font-size: 0.875rem; line-height: 1.6;">';

    for (const [key, value] of Object.entries(data)) {
        // Skip metadata fields
        if (key.startsWith('_') || key === 'enrichment_metadata') continue;

        html += formatField(key, value, 0);
    }

    html += '</div>';
    return html;
}

function formatField(key, value, depth) {
    const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const indent = depth * 20;

    let html = '';

    if (value === null || value === undefined || value === '') {
        return ''; // Skip empty values
    }

    if (typeof value === 'object' && !Array.isArray(value)) {
        // Nested object - make it collapsible
        const hasContent = Object.keys(value).length > 0;
        if (!hasContent) return '';

        html += `
            <details ${depth === 0 ? 'open' : ''} style="margin-bottom: 0.75rem; margin-left: ${indent}px; background: ${depth === 0 ? 'var(--gray-50)' : 'white'}; padding: 0.75rem; border-radius: 8px; border: 1px solid var(--gray-200);">
                <summary style="font-weight: 700; color: var(--gray-900); cursor: pointer; margin-bottom: 0.5rem;">
                    📁 ${label}
                </summary>
                <div style="margin-left: 1rem;">
        `;

        for (const [nestedKey, nestedValue] of Object.entries(value)) {
            html += formatField(nestedKey, nestedValue, depth + 1);
        }

        html += '</div></details>';

    } else if (Array.isArray(value)) {
        if (value.length === 0) return '';

        html += `
            <details ${depth === 0 ? 'open' : ''} style="margin-bottom: 0.75rem; margin-left: ${indent}px; background: ${depth === 0 ? 'var(--gray-50)' : 'white'}; padding: 0.75rem; border-radius: 8px; border: 1px solid var(--gray-200);">
                <summary style="font-weight: 700; color: var(--gray-900); cursor: pointer;">
                    📋 ${label} <span style="font-weight: 400; color: var(--gray-600);">(${value.length} items)</span>
                </summary>
                <div style="margin-left: 1rem; margin-top: 0.5rem;">
        `;

        if (typeof value[0] === 'object') {
            // Array of objects
            value.forEach((item, idx) => {
                html += `
                    <details style="margin-bottom: 0.5rem; background: white; padding: 0.75rem; border-radius: 6px; border: 1px solid var(--gray-300);">
                        <summary style="font-weight: 600; cursor: pointer; color: var(--gray-800);">Item ${idx + 1}</summary>
                        <div style="margin-top: 0.5rem; margin-left: 0.5rem; font-size: 0.9em;">
                `;
                for (const [k, v] of Object.entries(item)) {
                    const itemLabel = k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    html += `<div style="margin-bottom: 0.25rem;"><span style="font-weight: 600; color: var(--gray-700);">${itemLabel}:</span> <span style="color: var(--gray-900);">${escapeHtml(v) || 'N/A'}</span></div>`;
                }
                html += '</div></details>';
            });
        } else {
            // Array of primitives
            html += '<ul style="margin: 0.25rem 0; padding-left: 1.5rem;">';
            value.forEach(item => {
                html += `<li style="margin-bottom: 0.25rem; color: var(--gray-900);">${escapeHtml(item)}</li>`;
            });
            html += '</ul>';
        }

        html += '</div></details>';

    } else {
        // Simple value
        html += `
            <div style="margin-bottom: 0.5rem; margin-left: ${indent}px; padding: 0.5rem; background: white; border-radius: 6px; border-left: 3px solid var(--primary);">
                <div style="font-weight: 600; color: var(--gray-700); font-size: 0.75rem; margin-bottom: 0.25rem;">${label}</div>
                <div style="color: var(--gray-900);">
        `;

        if (typeof value === 'boolean') {
            html += value ? '✅ Yes' : '❌ No';
        } else if (typeof value === 'number') {
            html += `<span style="font-weight: 600;">${value}</span>`;
        } else if (typeof value === 'string' && value.startsWith('http')) {
            // URL - make it clickable
            html += `<a href="${escapeHtml(value)}" target="_blank" style="color: var(--primary); text-decoration: none; border-bottom: 1px solid var(--primary);">${escapeHtml(value)}</a>`;
        } else {
            html += escapeHtml(value);
        }

        html += '</div></div>';
    }

    return html;
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
