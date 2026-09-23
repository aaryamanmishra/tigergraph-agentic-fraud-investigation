/**
 * TigerGraph Agentic Fraud Console — Client Interactivity
 * Enhanced with D3.js force-directed evidence graph renderer.
 *
 * IMPORTANT: All graph data comes from /api/graph/<case_id> which is
 * built from actual evidence entity_ids in the stored benchmark result.
 * No data is fabricated.
 */

// Navigate to selected case from dropdown
function navigateToCase(caseId) {
    if (caseId) {
        window.location.href = '/case/' + encodeURIComponent(caseId);
    }
}

// Copy Raw JSON to clipboard
function copyRawJson() {
    const jsonBlock = document.getElementById('raw-json-block');
    if (!jsonBlock) return;

    const text = jsonBlock.innerText;
    navigator.clipboard.writeText(text).then(() => {
        const copyBtn = document.querySelector('.btn-copy');
        if (copyBtn) {
            const originalText = copyBtn.innerText;
            copyBtn.innerText = 'Copied! ✓';
            setTimeout(() => {
                copyBtn.innerText = originalText;
            }, 1800);
        }
    }).catch(err => {
        console.error('Failed to copy JSON:', err);
    });
}

// Keyboard shortcuts for fast presentation navigation: ArrowLeft (prev), ArrowRight (next)
document.addEventListener('keydown', function(event) {
    // Ignore if focus is in an input or select
    if (['input', 'textarea', 'select'].includes(document.activeElement.tagName.toLowerCase())) {
        return;
    }

    if (event.key === 'ArrowLeft') {
        const prevBtn = document.getElementById('btn-prev');
        if (prevBtn && prevBtn.tagName.toLowerCase() === 'a' && prevBtn.href) {
            window.location.href = prevBtn.href;
        }
    } else if (event.key === 'ArrowRight') {
        const nextBtn = document.getElementById('btn-next');
        if (nextBtn && nextBtn.tagName.toLowerCase() === 'a' && nextBtn.href) {
            window.location.href = nextBtn.href;
        }
    }
});

// ============================================================================
// D3.js FORCE-DIRECTED EVIDENCE GRAPH
// All node/edge data comes from /api/graph/<case_id> — real evidence data only.
// ============================================================================

// Node colors by entity type
const NODE_COLORS = {
    transaction: '#f59e0b',
    card:        '#38bdf8',
    customer:    '#10b981',
    device:      '#ef4444',
    closed_case: '#a78bfa',
    inference:   '#64748b',
    entity:      '#475569',
    graph:       '#94a3b8',
};

// Node radii by entity type
const NODE_RADII = {
    transaction: 14,
    card:        16,
    customer:    12,
    device:      18,
    closed_case: 13,
    inference:   10,
    entity:      10,
    graph:       10,
};

function initEvidenceGraph(caseId) {
    const container = document.getElementById('graph-container');
    const svgEl = document.getElementById('evidence-graph');
    const loadingEl = document.getElementById('graph-loading');
    const tooltip = document.getElementById('graph-tooltip');

    if (!container || !svgEl || typeof d3 === 'undefined') {
        if (loadingEl) loadingEl.textContent = 'D3.js not loaded — graph unavailable offline.';
        return;
    }

    // Fetch graph data from /api/graph/<case_id>
    fetch('/api/graph/' + encodeURIComponent(caseId))
        .then(r => r.json())
        .then(data => {
            if (loadingEl) loadingEl.style.display = 'none';

            const nodes = data.nodes || [];
            const links = data.links || [];

            if (nodes.length === 0) {
                if (loadingEl) {
                    loadingEl.style.display = 'block';
                    loadingEl.textContent = 'No entity data available for this case.';
                }
                return;
            }

            renderGraph(svgEl, container, nodes, links, tooltip);
        })
        .catch(err => {
            console.error('Graph fetch error:', err);
            if (loadingEl) {
                loadingEl.style.display = 'block';
                loadingEl.textContent = 'Could not load graph data.';
            }
        });
}

function renderGraph(svgEl, container, nodes, links, tooltip) {
    const W = container.clientWidth || 800;
    const H = container.clientHeight || 380;

    const svg = d3.select(svgEl)
        .attr('viewBox', `0 0 ${W} ${H}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    // Clear any previous render
    svg.selectAll('*').remove();

    // Zoom & pan
    const g = svg.append('g').attr('class', 'graph-root');
    svg.call(d3.zoom()
        .scaleExtent([0.3, 4])
        .on('zoom', (event) => g.attr('transform', event.transform))
    );

    // Arrowhead marker for directed edges
    svg.append('defs').append('marker')
        .attr('id', 'arrow')
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', '#2d3d56');

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links)
            .id(d => d.id)
            .distance(d => {
                // Longer distance for device→card links (important relationships)
                const src = d.source.type || '';
                const tgt = d.target.type || '';
                if (src === 'device' || tgt === 'device') return 120;
                if (src === 'closed_case' || tgt === 'closed_case') return 90;
                return 70;
            })
            .strength(0.4)
        )
        .force('charge', d3.forceManyBody().strength(-200).distanceMax(300))
        .force('center', d3.forceCenter(W / 2, H / 2))
        .force('collide', d3.forceCollide(d => (NODE_RADII[d.type] || 12) + 8))
        .force('x', d3.forceX(W / 2).strength(0.04))
        .force('y', d3.forceY(H / 2).strength(0.04));

    // Links
    const link = g.append('g').attr('class', 'links')
        .selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('class', 'g-link')
        .attr('marker-end', 'url(#arrow)');

    // Link labels (relation name)
    const linkLabel = g.append('g').attr('class', 'link-labels')
        .selectAll('text')
        .data(links)
        .enter().append('text')
        .attr('font-size', '7px')
        .attr('fill', '#4a5568')
        .attr('text-anchor', 'middle')
        .text(d => d.relation ? d.relation.slice(0, 18) : '');

    // Node groups
    const node = g.append('g').attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .enter().append('g')
        .attr('class', 'g-node')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded)
        );

    // Node circles
    node.append('circle')
        .attr('r', d => NODE_RADII[d.type] || 12)
        .attr('fill', d => NODE_COLORS[d.type] || '#475569')
        .attr('fill-opacity', 0.85)
        .attr('stroke', d => NODE_COLORS[d.type] || '#475569')
        .on('mouseover', function(event, d) {
            // Show tooltip
            tooltip.style.opacity = '1';
            tooltip.innerHTML = `
                <strong>${d.label || d.id}</strong><br>
                <span style="color:#94a3b8;">Type: ${d.type}</span><br>
                <span style="color:#94a3b8;font-size:0.7rem;">${d.id}</span>
            `;
        })
        .on('mousemove', function(event) {
            const rect = container.getBoundingClientRect();
            let left = event.clientX - rect.left + 12;
            let top = event.clientY - rect.top - 8;
            // Keep tooltip inside container
            if (left + 270 > W) left = left - 280;
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        })
        .on('mouseout', function() {
            tooltip.style.opacity = '0';
        })
        .on('click', function(event, d) {
            highlightNodeAndEvidence(d, node, link);
        });

    // Node labels
    node.append('text')
        .attr('dy', d => (NODE_RADII[d.type] || 12) + 10)
        .attr('text-anchor', 'middle')
        .text(d => {
            const lbl = d.label || d.id;
            return lbl.length > 16 ? lbl.slice(0, 14) + '…' : lbl;
        });

    // Simulation tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        linkLabel
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}

/**
 * When a graph node is clicked, highlight it + edges connected to it,
 * and highlight corresponding evidence cards on the page.
 */
function highlightNodeAndEvidence(clickedNode, node, link) {
    const nodeId = clickedNode.id;

    // Toggle: if already highlighted, clear all highlights
    const wasHighlighted = clickedNode._highlighted;
    clearAllHighlights(node, link);

    if (wasHighlighted) return;

    // Mark node as highlighted
    clickedNode._highlighted = true;

    // Highlight node circles
    node.select('circle')
        .attr('stroke-width', d => d.id === nodeId ? 4 : 2)
        .attr('fill-opacity', d => d.id === nodeId ? 1.0 : 0.4);

    // Highlight connected links
    link.each(function(d) {
        const srcId = typeof d.source === 'object' ? d.source.id : d.source;
        const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
        if (srcId === nodeId || tgtId === nodeId) {
            d3.select(this).classed('highlighted', true);
        } else {
            d3.select(this).attr('stroke-opacity', 0.15);
        }
    });

    // Highlight evidence cards containing this entity
    document.querySelectorAll('.entity-tag').forEach(tag => {
        if (tag.dataset.entity === nodeId) {
            const card = tag.closest('.evidence-card');
            if (card) {
                card.classList.add('highlighted');
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    });
}

function clearAllHighlights(node, link) {
    // Reset all nodes
    if (node) {
        node.each(d => { d._highlighted = false; });
        node.select('circle')
            .attr('stroke-width', 2)
            .attr('fill-opacity', 0.85);
    }

    // Reset all links
    if (link) {
        link.classed('highlighted', false)
            .attr('stroke-opacity', 0.7);
    }

    // Remove evidence card highlights
    document.querySelectorAll('.evidence-card.highlighted').forEach(card => {
        card.classList.remove('highlighted');
    });
}
