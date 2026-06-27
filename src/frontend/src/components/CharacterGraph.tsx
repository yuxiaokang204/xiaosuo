import React, { useRef, useEffect, useState, useCallback } from "react";

// ──────────── 类型定义 ────────────

export interface CharacterNode {
  id: string;
  name: string;
  role: string;
  color: string;
  description?: string;
}

export interface RelationshipEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface CharacterGraphProps {
  nodes: CharacterNode[];
  edges: RelationshipEdge[];
  width?: number;
  height?: number;
}

// ──────────── 常量 ────────────

const DEFAULT_COLORS = [
  "#667eea", "#764ba2", "#f093fb", "#4facfe",
  "#43e97b", "#fa709a", "#fee140", "#a18cd1",
  "#fbc2eb", "#8fd3f4", "#ff9a9e", "#fad0c4",
];

const ROLE_COLORS: Record<string, string> = {
  "主角": "#667eea",
  "protagonist": "#667eea",
  "反派": "#ef4444",
  "antagonist": "#ef4444",
  "配角": "#10b981",
  "导师": "#f59e0b",
  "mentor": "#f59e0b",
  "盟友": "#8b5cf6",
  "ally": "#8b5cf6",
  "路人": "#9ca3af",
};

const EDGE_COLORS: Record<string, string> = {
  "朋友": "#10b981",
  "敌人": "#ef4444",
  "恋人": "#ec4899",
  "师徒": "#f59e0b",
  "亲人": "#8b5cf6",
  "同事": "#3b82f6",
  "盟友": "#10b981",
};

// ──────────── 样式 ────────────

const S: Record<string, React.CSSProperties> = {
  container: {
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    overflow: "hidden",
  },
  header: {
    padding: "16px 20px",
    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
    color: "#fff",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 700,
  },
  canvasWrapper: {
    position: "relative",
    width: "100%",
    height: 500,
    background: "linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)",
    cursor: "grab",
  },
  canvasWrapperDragging: {
    cursor: "grabbing",
  },
  svg: {
    width: "100%",
    height: "100%",
  },
  legend: {
    padding: "12px 20px",
    borderTop: "1px solid #e5e7eb",
    display: "flex",
    flexWrap: "wrap",
    gap: 12,
  },
  legendTitle: {
    fontSize: 12,
    fontWeight: 600,
    color: "#6b7280",
    marginRight: 8,
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    fontSize: 11,
    color: "#4b5563",
  },
  emptyState: {
    textAlign: "center",
    padding: "60px 20px",
    color: "#9ca3af",
    fontSize: 14,
  },
  tooltip: {
    position: "absolute",
    background: "#1f2937",
    color: "#fff",
    padding: "8px 12px",
    borderRadius: 8,
    fontSize: 12,
    lineHeight: 1.5,
    pointerEvents: "none",
    zIndex: 100,
    maxWidth: 200,
    boxShadow: "0 4px 12px rgba(0,0,0,.2)",
  },
};

// ──────────── 物理模拟 ────────────

interface SimNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  data: CharacterNode;
}

function initializeSimulation(
  nodes: CharacterNode[],
  width: number,
  height: number
): SimNode[] {
  const simNodes: SimNode[] = nodes.map((node) => ({
    x: width / 2 + (Math.random() - 0.5) * 200,
    y: height / 2 + (Math.random() - 0.5) * 200,
    vx: 0,
    vy: 0,
    radius: 32,
    data: node,
  }));

  return simNodes;
}

function simulateForwards(
  nodes: SimNode[],
  edges: RelationshipEdge[],
  width: number,
  height: number,
  iterations: number
) {
  const k = Math.sqrt((width * height) / nodes.length) * 0.8;

  for (let iter = 0; iter < iterations; iter++) {
    // 斥力
    for (let i = 0; i < nodes.length; i++) {
      nodes[i].vx = 0;
      nodes[i].vy = 0;
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (k * k) / dist;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx;
        nodes[i].vy -= fy;
        nodes[j].vx += fx;
        nodes[j].vy += fy;
      }
    }

    // 引力（边）
    for (const edge of edges) {
      const source = nodes.find((n) => n.data.id === edge.source);
      const target = nodes.find((n) => n.data.id === edge.target);
      if (!source || !target) continue;

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist * dist) / k;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      source.vx += fx;
      source.vy += fy;
      target.vx -= fx;
      target.vy -= fy;
    }

    // 中心引力
    for (const node of nodes) {
      const dx = width / 2 - node.x;
      const dy = height / 2 - node.y;
      node.vx += dx * 0.01;
      node.vy += dy * 0.01;
    }

    // 更新位置
    for (const node of nodes) {
      node.x += node.vx * 0.3;
      node.y += node.vy * 0.3;
      node.x = Math.max(node.radius, Math.min(width - node.radius, node.x));
      node.y = Math.max(node.radius, Math.min(height - node.radius, node.y));
    }
  }
}

// ──────────── 子组件 ────────────

function NodeComponent({
  node,
  hovered,
  onHover,
  onClick,
}: {
  node: SimNode;
  hovered: boolean;
  onHover: (id: string | null) => void;
  onClick: (node: CharacterNode) => void;
}) {
  const color = ROLE_COLORS[node.data.role] || node.data.color || DEFAULT_COLORS[0];

  return (
    <g
      onMouseEnter={() => onHover(node.data.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(node.data)}
      style={{ cursor: "pointer" }}
    >
      {/* 外发光 */}
      <circle
        cx={node.x}
        cy={node.y}
        r={node.radius + 4}
        fill={color}
        opacity={hovered ? 0.2 : 0}
        style={{ transition: "opacity .2s" }}
      />
      {/* 主圆 */}
      <circle
        cx={node.x}
        cy={node.y}
        r={node.radius}
        fill={color}
        stroke="#fff"
        strokeWidth={3}
        filter="url(#nodeShadow)"
      />
      {/* 首字 */}
      <text
        x={node.x}
        y={node.y}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#fff"
        fontSize={16}
        fontWeight={700}
        style={{ pointerEvents: "none" }}
      >
        {node.data.name.charAt(0)}
      </text>
      {/* 名称标签 */}
      <text
        x={node.x}
        y={node.y + node.radius + 16}
        textAnchor="middle"
        fill="#1f2937"
        fontSize={11}
        fontWeight={600}
        style={{ pointerEvents: "none" }}
      >
        {node.data.name}
      </text>
      {/* 角色标签 */}
      <text
        x={node.x}
        y={node.y + node.radius + 28}
        textAnchor="middle"
        fill="#6b7280"
        fontSize={9}
        style={{ pointerEvents: "none" }}
      >
        {node.data.role}
      </text>
    </g>
  );
}

function EdgeComponent({
  edge,
  nodes,
  hovered,
}: {
  edge: RelationshipEdge;
  nodes: SimNode[];
  hovered: boolean;
}) {
  const source = nodes.find((n) => n.data.id === edge.source);
  const target = nodes.find((n) => n.data.id === edge.target);
  if (!source || !target) return null;

  const color = EDGE_COLORS[edge.type] || "#94a3b8";

  return (
    <g>
      {/* 连线 */}
      <line
        x1={source.x}
        y1={source.y}
        x2={target.x}
        y2={target.y}
        stroke={color}
        strokeWidth={hovered ? 3 : 2}
        strokeDasharray={edge.type === "敌人" ? "6,4" : "none"}
        opacity={hovered ? 1 : 0.6}
        style={{ transition: "all .2s" }}
      />
      {/* 关系类型标签（连线中点） */}
      <rect
        x={(source.x + target.x) / 2 - 20}
        y={(source.y + target.y) / 2 - 8}
        width={40}
        height={16}
        rx={8}
        fill={color}
        opacity={0.9}
      />
      <text
        x={(source.x + target.x) / 2}
        y={(source.y + target.y) / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#fff"
        fontSize={9}
        fontWeight={600}
        style={{ pointerEvents: "none" }}
      >
        {edge.type}
      </text>
    </g>
  );
}

// ──────────── 主组件 ────────────

export const CharacterGraph: React.FC<CharacterGraphProps> = ({
  nodes,
  edges,
  width = 800,
  height = 500,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<CharacterNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragNodeRef = useRef<string | null>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);

  // 初始化物理模拟
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      return;
    }

    const sim = initializeSimulation(nodes, width, height);
    simulateForwards(sim, edges, width, height, 150);
    setSimNodes(sim);
  }, [nodes, edges, width, height]);

  // 处理节点悬停
  const handleNodeHover = useCallback((id: string | null) => {
    setHoveredId(id);
  }, []);

  const handleNodeMouseOver = useCallback(
    (node: SimNode, e: React.MouseEvent) => {
      setHoveredNode(node.data);
      setTooltipPos({ x: e.clientX + 12, y: e.clientY - 12 });
    },
    []
  );

  const handleNodeMouseOut = useCallback(() => {
    setHoveredNode(null);
  }, []);

  // 处理拖拽
  const handleMouseDown = useCallback(
    (nodeId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setIsDragging(true);
      dragNodeRef.current = nodeId;
      const node = simNodes.find((n) => n.data.id === nodeId);
      if (node) {
        dragOffsetRef.current = { x: node.x, y: node.y };
      }
    },
    [simNodes]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging || !dragNodeRef.current) return;
      const svg = svgRef.current;
      if (!svg) return;

      const rect = svg.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left - panOffset.x) / zoom;
      const mouseY = (e.clientY - rect.top - panOffset.y) / zoom;

      setSimNodes((prev) =>
        prev.map((n) => {
          if (n.data.id === dragNodeRef.current) {
            return {
              ...n,
              x: mouseX - dragOffsetRef.current.x + n.x,
              y: mouseY - dragOffsetRef.current.y + n.y,
            };
          }
          return n;
        })
      );
    },
    [isDragging, panOffset, zoom]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    dragNodeRef.current = null;
  }, []);

  // 处理滚轮缩放
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const newZoom = Math.max(0.5, Math.min(2, zoom - e.deltaY * 0.001));
      setZoom(newZoom);
    },
    [zoom]
  );

  const hoveredEdges = edges.filter(
    (e) =>
      hoveredId &&
      (e.source === hoveredId || e.target === hoveredId)
  );

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerTitle}>
          👥 角色关系图谱
          {nodes.length > 0 && (
            <span style={{ marginLeft: 8, opacity: 0.85, fontWeight: 400 }}>
              ({nodes.length} 角色 / {edges.length} 关系)
            </span>
          )}
        </div>
      </div>

      {nodes.length === 0 ? (
        <div style={S.emptyState}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🕸️</div>
          <div>暂无角色关系数据</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            添加角色和关系后，图谱将自动显示
          </div>
        </div>
      ) : (
        <>
          <div
            style={{
              ...S.canvasWrapper,
              ...(isDragging ? S.canvasWrapperDragging : {}),
            }}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <svg
              ref={svgRef}
              style={S.svg}
              onWheel={handleWheel}
            >
              <defs>
                <filter id="nodeShadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15" />
                </filter>
              </defs>
              <g
                transform={`translate(${panOffset.x},${panOffset.y}) scale(${zoom})`}
              >
                {/* 关系连线 */}
                {edges.map((edge) => (
                  <EdgeComponent
                    key={edge.id}
                    edge={edge}
                    nodes={simNodes}
                    hovered={
                      !hoveredId ||
                      hoveredEdges.some((e) => e.id === edge.id)
                    }
                  />
                ))}
                {/* 角色节点 */}
                {simNodes.map((node) => (
                  <g
                    key={node.data.id}
                    onMouseDown={(e) => handleMouseDown(node.data.id, e)}
                    onMouseOver={(e) => handleNodeMouseOver(node, e)}
                    onMouseOut={handleNodeMouseOut}
                  >
                    <NodeComponent
                      node={node}
                      hovered={hoveredId === node.data.id}
                      onHover={handleNodeHover}
                      onClick={() => setHoveredNode(node.data)}
                    />
                  </g>
                ))}
              </g>
            </svg>

            {/* 悬停提示框 */}
            {hoveredNode && (
              <div
                style={{
                  ...S.tooltip,
                  left: Math.min(tooltipPos.x, window.innerWidth - 220),
                  top: Math.min(tooltipPos.y, window.innerHeight - 100),
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 4 }}>
                  {hoveredNode.name}
                </div>
                <div style={{ opacity: 0.8 }}>
                  {hoveredNode.role}
                </div>
                {hoveredNode.description && (
                  <div style={{ marginTop: 4, opacity: 0.7 }}>
                    {hoveredNode.description}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 图例 */}
          <div style={S.legend}>
            <span style={S.legendTitle}>关系类型:</span>
            {Array.from(new Set(edges.map((e) => e.type))).map((type) => (
              <span key={type} style={S.legendItem}>
                <span
                  style={{
                    width: 10,
                    height: 3,
                    borderRadius: 2,
                    background: EDGE_COLORS[type] || "#94a3b8",
                    display: "inline-block",
                  }}
                />
                {type}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
