/**
 * Workflow graph visualization using SVG
 */

import { escapeHtml } from '../utils.js';
import { dom } from '../state.js';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 60;
const NODE_PADDING = 20;
const LEVEL_HEIGHT = 120;

const CATEGORY_COLORS = {
    'Models': { bg: '#7c6aef', text: '#fff' },
    'Prompts': { bg: '#4ade80', text: '#000' },
    'Sampler': { bg: '#fb923c', text: '#000' },
    'Image Settings': { bg: '#60a5fa', text: '#000' },
    'Post Processing': { bg: '#f472b6', text: '#000' },
    'LoRA': { bg: '#22d3ee', text: '#000' },
    'Other': { bg: '#8888a0', text: '#000' }
};

export function renderWorkflowGraph(workflow) {
    if (!workflow || !workflow.workflow_nodes) {
        return '<div class="empty-state"><p>No workflow data available</p></div>';
    }

    const nodes = [];
    const connections = [];

    // Flatten workflow nodes
    for (const [category, categoryNodes] of Object.entries(workflow.workflow_nodes)) {
        categoryNodes.forEach(node => {
            nodes.push({
                ...node,
                category,
                color: CATEGORY_COLORS[category] || CATEGORY_COLORS['Other']
            });
        });
    }

    // Build connections from inputs
    nodes.forEach(node => {
        if (node.inputs) {
            for (const [key, value] of Object.entries(node.inputs)) {
                // Check if value is a link to another node
                if (Array.isArray(value) && value.length === 2) {
                    const [sourceNodeId] = value;
                    const sourceNode = nodes.find(n => String(n.node_id) === String(sourceNodeId));
                    if (sourceNode) {
                        connections.push({
                            from: sourceNode,
                            to: node,
                            label: key
                        });
                    }
                }
            }
        }
    });

    // Layout nodes in levels
    const levels = layoutNodes(nodes, connections);

    // Calculate dimensions
    const maxNodesInLevel = Math.max(...levels.map(l => l.length));
    const svgWidth = maxNodesInLevel * (NODE_WIDTH + NODE_PADDING) + NODE_PADDING * 2;
    const svgHeight = levels.length * LEVEL_HEIGHT + NODE_PADDING * 2;

    // Generate SVG
    let svg = `<svg class="workflow-svg" viewBox="0 0 ${svgWidth} ${svgHeight}" xmlns="http://www.w3.org/2000/svg">`;

    // Defs for gradients and markers
    svg += `
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#8888a0"/>
            </marker>
            <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.3"/>
            </filter>
        </defs>
    `;

    // Draw connections
    connections.forEach(conn => {
        const fromPos = getNodePosition(conn.from, levels);
        const toPos = getNodePosition(conn.to, levels);

        if (fromPos && toPos) {
            const x1 = fromPos.x + NODE_WIDTH;
            const y1 = fromPos.y + NODE_HEIGHT / 2;
            const x2 = toPos.x;
            const y2 = toPos.y + NODE_HEIGHT / 2;

            // Curved path
            const midX = (x1 + x2) / 2;
            svg += `<path 
                class="workflow-connection" 
                d="M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}" 
                stroke="#8888a0" 
                stroke-width="2" 
                fill="none" 
                marker-end="url(#arrowhead)"
            />`;
        }
    });

    // Draw nodes
    levels.forEach((level, levelIdx) => {
        level.forEach((node, nodeIdx) => {
            const x = NODE_PADDING + nodeIdx * (NODE_WIDTH + NODE_PADDING);
            const y = NODE_PADDING + levelIdx * LEVEL_HEIGHT;

            svg += renderNode(node, x, y);
        });
    });

    svg += '</svg>';

    return `
        <div class="workflow-graph-container">
            <div class="workflow-graph-header">
                <h4>Workflow Graph</h4>
                <span class="text-dim">${nodes.length} nodes</span>
            </div>
            <div class="workflow-graph" id="workflow-graph">
                ${svg}
            </div>
        </div>
    `;
}

function renderNode(node, x, y) {
    const color = node.color || CATEGORY_COLORS['Other'];
    const inputs = node.inputs ? Object.entries(node.inputs) : [];

    let g = `<g class="workflow-node" transform="translate(${x}, ${y})" data-node-id="${node.node_id}">`;
    
    // Node background
    g += `<rect 
        x="0" y="0" 
        width="${NODE_WIDTH}" height="${NODE_HEIGHT}" 
        rx="8" ry="8" 
        fill="#1a1a24" 
        stroke="${color.bg}" 
        stroke-width="2"
        filter="url(#node-shadow)"
    />`;
    
    // Category badge
    g += `<rect 
        x="0" y="0" 
        width="8" height="${NODE_HEIGHT}" 
        rx="8" ry="0"
        fill="${color.bg}"
    />`;
    
    // Title
    g += `<text 
        x="16" y="22" 
        fill="#e0e0e8" 
        font-size="12" 
        font-weight="600"
        font-family="'Segoe UI', system-ui, sans-serif"
    >${escapeHtml(node.title || node.class_type)}</text>`;
    
    // Class type
    g += `<text 
        x="16" y="40" 
        fill="#8888a0" 
        font-size="10"
        font-family="'Segoe UI', system-ui, sans-serif"
    >${escapeHtml(node.class_type)}</text>`;
    
    // Node ID
    g += `<text 
        x="${NODE_WIDTH - 8}" y="22" 
        fill="#5a5a70" 
        font-size="10" 
        text-anchor="end"
        font-family="'Segoe UI', system-ui, sans-serif"
    >#${escapeHtml(node.node_id)}</text>`;
    
    // Input dots
    inputs.slice(0, 3).forEach((input, idx) => {
        g += `<circle 
            cx="0" cy="${20 + idx * 15}" 
            r="4" 
            fill="#2e2e3e"
            stroke="${color.bg}"
            stroke-width="1"
        />`;
    });

    // Output dot
    g += `<circle 
        cx="${NODE_WIDTH}" cy="${NODE_HEIGHT / 2}" 
        r="4" 
        fill="${color.bg}"
    />`;
    
    g += '</g>';
    return g;
}

function layoutNodes(nodes, _connections) {
    // Simple layout: group by category
    const levels = [];
    const categories = {};

    nodes.forEach(node => {
        if (!categories[node.category]) {
            categories[node.category] = [];
        }
        categories[node.category].push(node);
    });

    // Order categories
    const categoryOrder = ['Prompts', 'Models', 'LoRA', 'Sampler', 'Image Settings', 'Post Processing', 'Other'];
    
    categoryOrder.forEach(cat => {
        if (categories[cat] && categories[cat].length > 0) {
            levels.push(categories[cat]);
        }
    });

    return levels;
}

function getNodePosition(node, levels) {
    for (let levelIdx = 0; levelIdx < levels.length; levelIdx++) {
        const level = levels[levelIdx];
        for (let nodeIdx = 0; nodeIdx < level.length; nodeIdx++) {
            if (level[nodeIdx].node_id === node.node_id) {
                return {
                    x: NODE_PADDING + nodeIdx * (NODE_WIDTH + NODE_PADDING),
                    y: NODE_PADDING + levelIdx * LEVEL_HEIGHT
                };
            }
        }
    }
    return null;
}

export function initWorkflowGraphEvents() {
    const container = dom.workflowGraph;
    if (!container) return;

    let isPanning = false;
    let startX, startY, scrollLeft, scrollTop;

    container.addEventListener('mousedown', (e) => {
        if (e.target.closest('.workflow-node')) return;
        isPanning = true;
        container.style.cursor = 'grabbing';
        startX = e.pageX - container.offsetLeft;
        startY = e.pageY - container.offsetTop;
        scrollLeft = container.scrollLeft;
        scrollTop = container.scrollTop;
    });

    container.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        e.preventDefault();
        const x = e.pageX - container.offsetLeft;
        const y = e.pageY - container.offsetTop;
        container.scrollLeft = scrollLeft - (x - startX);
        container.scrollTop = scrollTop - (y - startY);
    });

    container.addEventListener('mouseup', () => {
        isPanning = false;
        container.style.cursor = '';
    });

    container.addEventListener('mouseleave', () => {
        isPanning = false;
        container.style.cursor = '';
    });

    // Node click
    container.querySelectorAll('.workflow-node').forEach(node => {
        node.addEventListener('click', () => {
            node.classList.toggle('selected');
        });
    });
}
