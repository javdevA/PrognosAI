/**
 * graph.js
 * D3.js disease cascade graph.
 *
 * Layout: nodes are grouped vertically by category so the cascade
 * flows top-to-bottom like a proper DAG:
 *   habit_risk (top) -> condition -> disease -> severe -> terminal (bottom)
 */

const CATEGORY_COLOR = {
  habit_risk: '#BA7517',
  condition:  '#534AB7',
  disease:    '#1D9E75',
  severe:     '#D85A30',
  terminal:   '#A32D2D',
};

const CATEGORY_RADIUS = {
  habit_risk: 26,
  condition:  23,
  disease:    21,
  severe:     24,
  terminal:   28,
};

const CATEGORY_LAYER = {
  habit_risk: 0.1,
  condition:  0.3,
  disease:    0.55,
  severe:     0.75,
  terminal:   0.92,
};

let simulationInstance = null;
let animationFired = false;
let fallbackTimer = null;

function drawDiseaseGraph(graphData, nodeAnnotations, worstPath) {
  if (simulationInstance) { simulationInstance.stop(); simulationInstance = null; }
  if (fallbackTimer) { clearTimeout(fallbackTimer); fallbackTimer = null; }
  animationFired = false;
  d3.select('#graph-tooltip-singleton').remove();

  const container = document.getElementById('graph-container');
  container.innerHTML = '';

  const W = container.clientWidth || 720;
  const H = 540;

  const svg = d3.select('#graph-container')
    .append('svg')
    .attr('width', '100%')
    .attr('height', H)
    .attr('viewBox', `0 0 ${W} ${H}`);

  const defs = svg.append('defs');

  ['graph-arrow', 'graph-arrow-red'].forEach((id, isRed) => {
    defs.append('marker')
      .attr('id', id)
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 22).attr('refY', 5)
      .attr('markerWidth', 5).attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M2 2L8 5L2 8')
      .attr('fill', 'none')
      .attr('stroke', isRed ? '#E24B4A' : '#C0BDB5')
      .attr('stroke-width', 1.5)
      .attr('stroke-linecap', 'round');
  });

  const filter = defs.append('filter').attr('id', 'glow');
  filter.append('feGaussianBlur').attr('stdDeviation', 5).attr('result', 'coloredBlur');
  const merge = filter.append('feMerge');
  merge.append('feMergeNode').attr('in', 'coloredBlur');
  merge.append('feMergeNode').attr('in', 'SourceGraphic');

  const zoomGroup = svg.append('g');
  const zoomBehavior = d3.zoom().scaleExtent([0.2, 3]).on('zoom', e => {
    zoomGroup.attr('transform', e.transform);
  });
  svg.call(zoomBehavior);

  const resetBtn = document.getElementById('btn-reset-zoom');
  if (resetBtn) {
    const newBtn = resetBtn.cloneNode(true);
    resetBtn.parentNode.replaceChild(newBtn, resetBtn);
    newBtn.addEventListener('click', () => {
      svg.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity);
    });
  }

  const worstPathSet = new Set(worstPath);

  const nodes = graphData.nodes.map(n => ({
    id: n.id,
    label: n.label,
    category: n.category,
    annotation: nodeAnnotations[n.id] || {},
    targetY: H * (CATEGORY_LAYER[n.category] || 0.5),
  }));

  const links = graphData.edges
    .filter(e => e.probability > 0.005)
    .map(e => ({
      source: e.from,
      target: e.to,
      probability: e.probability,
      onPath: worstPathSet.has(e.from) && worstPathSet.has(e.to),
    }));

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(80).strength(0.35))
    .force('charge', d3.forceManyBody().strength(-320))
    .force('centerX', d3.forceX(W / 2).strength(0.05))
    .force('layerY', d3.forceY(d => d.targetY).strength(0.5))
    .force('collision', d3.forceCollide().radius(d => (CATEGORY_RADIUS[d.category] || 22) + 12));

  simulationInstance = simulation;

  const edgeGroup = zoomGroup.append('g');
  const link = edgeGroup.selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', d => d.onPath ? '#E24B4A' : '#D0CEC8')
    .attr('stroke-width', d => d.onPath ? Math.max(1.8, d.probability * 4) : Math.max(0.5, d.probability * 1.5))
    .attr('stroke-opacity', d => d.onPath ? 0.9 : 0.4)
    .attr('marker-end', d => d.onPath ? 'url(#graph-arrow-red)' : 'url(#graph-arrow)');

  const nodeGroup = zoomGroup.append('g');
  const node = nodeGroup.selectAll('g')
    .data(nodes)
    .enter().append('g')
    .attr('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.2).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    );

  node.append('circle')
    .attr('class', 'glow-ring')
    .attr('r', d => (CATEGORY_RADIUS[d.category] || 22) + 7)
    .attr('fill', 'none')
    .attr('stroke', '#E24B4A')
    .attr('stroke-width', 2)
    .attr('opacity', 0)
    .attr('filter', 'url(#glow)');

  node.append('circle')
    .attr('class', 'node-circle')
    .attr('r', d => CATEGORY_RADIUS[d.category] || 22)
    .attr('fill', d => (CATEGORY_COLOR[d.category] || '#888') + '18')
    .attr('stroke', d => CATEGORY_COLOR[d.category] || '#888')
    .attr('stroke-width', 1.5);

  node.append('text')
    .attr('text-anchor', 'middle')
    .attr('font-size', '8.5px')
    .attr('font-family', 'system-ui, sans-serif')
    .attr('fill', d => CATEGORY_COLOR[d.category] || '#444')
    .attr('font-weight', '500')
    .attr('pointer-events', 'none')
    .each(function(d) {
      const el = d3.select(this);
      const words = d.label.split(' ');
      if (words.length === 1) {
        el.append('tspan').attr('x', 0).attr('dy', '0.35em').text(d.label);
      } else if (words.length === 2) {
        el.append('tspan').attr('x', 0).attr('dy', '-0.3em').text(words[0]);
        el.append('tspan').attr('x', 0).attr('dy', '1.1em').text(words[1]);
      } else {
        const mid = Math.ceil(words.length / 2);
        el.append('tspan').attr('x', 0).attr('dy', '-0.3em').text(words.slice(0, mid).join(' '));
        el.append('tspan').attr('x', 0).attr('dy', '1.1em').text(words.slice(mid).join(' '));
      }
    });

  const tooltip = d3.select('body').append('div')
    .attr('id', 'graph-tooltip-singleton')
    .attr('class', 'graph-tooltip')
    .style('opacity', 0)
    .style('pointer-events', 'none');

  node.on('mouseover', (event, d) => {
    const ann = d.annotation;
    tooltip.html(`
      <div class="tt-name">${d.label}</div>
      <div class="tt-row"><b>Category:</b> ${d.category.replace(/_/g,' ')}</div>
      <div class="tt-row"><b>DP risk score:</b> ${ann.dp_score !== undefined ? ann.dp_score.toFixed(4) : '--'}</div>
      <div class="tt-row">${ann.on_worst_path ? '<span style="color:#E24B4A">On cascade path</span>' : 'Not on cascade path'}</div>
      ${ann.path_edge_risk > 0 ? `<div class="tt-row"><b>Edge probability:</b> ${ann.path_edge_risk.toFixed(4)}</div>` : ''}
    `)
    .style('opacity', 1)
    .style('left', (event.pageX + 14) + 'px')
    .style('top', (event.pageY - 12) + 'px');
  })
  .on('mousemove', event => {
    tooltip
      .style('left', (event.pageX + 14) + 'px')
      .style('top', (event.pageY - 12) + 'px');
  })
  .on('mouseout', () => { tooltip.style('opacity', 0); });

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function fireAnimation() {
    if (animationFired) return;
    animationFired = true;
    if (fallbackTimer) { clearTimeout(fallbackTimer); fallbackTimer = null; }
    animateCascade(node, worstPath);
  }

  simulation.on('end', fireAnimation);
  fallbackTimer = setTimeout(fireAnimation, 3000);
}

function animateCascade(nodeSelection, worstPath) {
  worstPath.forEach((nodeId, index) => {
    setTimeout(() => {
      const target = nodeSelection.filter(d => d.id === nodeId);
      target.select('.node-circle')
        .transition().duration(350)
        .attr('fill', '#E24B4A30')
        .attr('stroke', '#E24B4A')
        .attr('stroke-width', 3);
      target.select('.glow-ring')
        .transition().duration(250).attr('opacity', 0.7)
        .transition().duration(700).attr('opacity', 0.2);
      target.select('text')
        .transition().duration(250)
        .attr('fill', '#C0392B')
        .attr('font-weight', '700');
    }, index * 480);
  });
}