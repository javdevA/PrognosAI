/**
 * graph.js
 * D3.js force-directed graph visualization for the disease cascade.
 *
 * Features:
 *  - All 25 disease nodes rendered as labeled circles
 *  - Nodes colored by category: habit_risk, condition, disease, severe, terminal
 *  - Cascade path nodes animate red sequentially with a glow ring
 *  - Edge width proportional to probability
 *  - Zoom and pan enabled
 *  - Tooltip on hover showing node label, category, and DP score
 */

const CATEGORY_COLOR = {
  habit_risk: '#BA7517',   // amber — root habits
  condition:  '#534AB7',   // purple — intermediate conditions
  disease:    '#1D9E75',   // teal — established diseases
  severe:     '#D85A30',   // coral — severe outcomes
  terminal:   '#A32D2D',   // dark red — terminal states
};

const CATEGORY_RADIUS = {
  habit_risk: 28,
  condition:  24,
  disease:    22,
  severe:     26,
  terminal:   30,
};

let simulationInstance = null;

function drawDiseaseGraph(graphData, nodeAnnotations, worstPath) {
  // Clear previous render
  const container = document.getElementById('graph-container');
  container.innerHTML = '';
  if (simulationInstance) {
    simulationInstance.stop();
    simulationInstance = null;
  }

  const W = container.clientWidth || 680;
  const H = 540;

  const svg = d3.select('#graph-container')
    .append('svg')
    .attr('width', '100%')
    .attr('height', H)
    .attr('viewBox', `0 0 ${W} ${H}`);

  // Arrow marker definition
  svg.append('defs').append('marker')
    .attr('id', 'graph-arrow')
    .attr('viewBox', '0 0 10 10')
    .attr('refX', 22)
    .attr('refY', 5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto-start-reverse')
    .append('path')
    .attr('d', 'M2 1L8 5L2 9')
    .attr('fill', 'none')
    .attr('stroke', '#888780')
    .attr('stroke-width', 1.5)
    .attr('stroke-linecap', 'round')
    .attr('stroke-linejoin', 'round');

  // Glow filter for cascade nodes
  const defs = svg.select('defs');
  const filter = defs.append('filter').attr('id', 'glow');
  filter.append('feGaussianBlur').attr('stdDeviation', 4).attr('result', 'coloredBlur');
  const feMerge = filter.append('feMerge');
  feMerge.append('feMergeNode').attr('in', 'coloredBlur');
  feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

  // Zoom layer
  const zoomGroup = svg.append('g').attr('class', 'zoom-group');

  svg.call(d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => {
      zoomGroup.attr('transform', event.transform);
    })
  );

  document.getElementById('btn-reset-zoom').addEventListener('click', () => {
    svg.transition().duration(400).call(
      d3.zoom().transform,
      d3.zoomIdentity
    );
  });

  // Prepare nodes and links
  const nodes = graphData.nodes.map(n => ({
    id: n.id,
    label: n.label,
    category: n.category,
    annotation: nodeAnnotations[n.id] || {},
  }));

  const links = graphData.edges.map(e => ({
    source: e.from,
    target: e.to,
    probability: e.probability,
  }));

  const worstPathSet = new Set(worstPath);

  // Force simulation
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(90).strength(0.5))
    .force('charge', d3.forceManyBody().strength(-320))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => CATEGORY_RADIUS[d.category] + 12));

  simulationInstance = simulation;

  // Draw edges
  const edgeGroup = zoomGroup.append('g').attr('class', 'edges');
  const link = edgeGroup.selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', d => {
      const srcOnPath = worstPathSet.has(d.source.id || d.source);
      const dstOnPath = worstPathSet.has(d.target.id || d.target);
      return (srcOnPath && dstOnPath) ? '#E24B4A' : '#B4B2A9';
    })
    .attr('stroke-width', d => Math.max(0.8, d.probability * 3.5))
    .attr('stroke-opacity', d => {
      const srcOnPath = worstPathSet.has(d.source.id || d.source);
      const dstOnPath = worstPathSet.has(d.target.id || d.target);
      return (srcOnPath && dstOnPath) ? 0.85 : 0.35;
    })
    .attr('marker-end', 'url(#graph-arrow)');

  // Draw nodes
  const nodeGroup = zoomGroup.append('g').attr('class', 'nodes');
  const node = nodeGroup.selectAll('g')
    .data(nodes)
    .enter().append('g')
    .attr('class', 'graph-node')
    .attr('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    );

  // Outer glow ring (hidden initially, shown during cascade animation)
  node.append('circle')
    .attr('class', 'glow-ring')
    .attr('r', d => CATEGORY_RADIUS[d.category] + 7)
    .attr('fill', 'none')
    .attr('stroke', '#E24B4A')
    .attr('stroke-width', 2.5)
    .attr('opacity', 0)
    .attr('filter', 'url(#glow)');

  // Main node circle
  node.append('circle')
    .attr('class', 'node-circle')
    .attr('r', d => CATEGORY_RADIUS[d.category])
    .attr('fill', d => CATEGORY_COLOR[d.category] + '22')
    .attr('stroke', d => CATEGORY_COLOR[d.category])
    .attr('stroke-width', 1.5);

  // Node label
  node.append('text')
    .attr('class', 'node-label')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'central')
    .attr('font-size', d => d.label.length > 12 ? '9px' : '10px')
    .attr('font-family', 'system-ui, sans-serif')
    .attr('fill', d => CATEGORY_COLOR[d.category])
    .attr('font-weight', '500')
    .attr('pointer-events', 'none')
    .text(d => {
      // Truncate long labels to two lines
      const words = d.label.split(' ');
      return words.length <= 2 ? d.label : words.slice(0, 2).join(' ');
    });

  // Tooltip
  const tooltip = d3.select('body').append('div')
    .attr('class', 'graph-tooltip')
    .style('opacity', 0);

  node.on('mouseover', (event, d) => {
    const ann = d.annotation;
    tooltip
      .html(`
        <div class="tt-title">${d.label}</div>
        <div class="tt-row"><span>Category:</span> ${d.category.replace('_', ' ')}</div>
        <div class="tt-row"><span>DP Score:</span> ${ann.dp_score !== undefined ? ann.dp_score.toFixed(4) : '—'}</div>
        <div class="tt-row"><span>On worst path:</span> ${ann.on_worst_path ? '✓ Yes' : 'No'}</div>
        ${ann.path_edge_risk > 0 ? `<div class="tt-row"><span>Edge risk:</span> ${ann.path_edge_risk.toFixed(4)}</div>` : ''}
      `)
      .style('opacity', 1)
      .style('left', (event.pageX + 12) + 'px')
      .style('top', (event.pageY - 10) + 'px');
  })
  .on('mousemove', (event) => {
    tooltip.style('left', (event.pageX + 12) + 'px').style('top', (event.pageY - 10) + 'px');
  })
  .on('mouseout', () => {
    tooltip.style('opacity', 0);
  });

  // Update positions on simulation tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  // Fire cascade animation after simulation stabilizes
  simulation.on('end', () => {
    animateCascade(node, worstPath, 0);
  });

  // Fallback: start animation after 2.5s if simulation hasn't ended
  setTimeout(() => {
    if (simulationInstance) animateCascade(node, worstPath, 0);
  }, 2500);
}


function animateCascade(nodeSelection, worstPath, startIndex) {
  if (startIndex >= worstPath.length) return;

  const nodeId = worstPath[startIndex];
  const delay = startIndex * 500; // 500ms between each node lighting up

  setTimeout(() => {
    nodeSelection.filter(d => d.id === nodeId)
      .select('.node-circle')
      .transition()
      .duration(400)
      .attr('fill', '#E24B4A44')
      .attr('stroke', '#E24B4A')
      .attr('stroke-width', 3);

    nodeSelection.filter(d => d.id === nodeId)
      .select('.glow-ring')
      .transition()
      .duration(300)
      .attr('opacity', 0.7)
      .transition()
      .duration(400)
      .attr('opacity', 0.3);

    nodeSelection.filter(d => d.id === nodeId)
      .select('.node-label')
      .transition()
      .duration(300)
      .attr('fill', '#E24B4A')
      .attr('font-weight', '700');

    animateCascade(nodeSelection, worstPath, startIndex + 1);
  }, delay);
}
