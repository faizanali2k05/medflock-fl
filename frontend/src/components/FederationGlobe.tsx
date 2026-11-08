import { useEffect, useMemo, useRef, useState } from "react";
import type { Activity } from "../api";

type Point = [number, number, number];
const project = ([x, y, z]: Point, angle: number) => {
  const rotatedX = x * Math.cos(angle) + z * Math.sin(angle);
  const depth = z * Math.cos(angle) - x * Math.sin(angle);
  const scale = 126 / (1 - depth * 0.12);
  return [320 + rotatedX * scale, 185 + y * scale];
};

function WireSphere({ reduced }: { reduced: boolean }) {
  const lines = useRef<SVGPathElement[]>([]);
  const geometry = useMemo(() => {
    const paths: Point[][] = [];
    for (let latitude = 1; latitude < 12; latitude++) {
      const phi = (latitude / 12) * Math.PI;
      paths.push(
        Array.from({ length: 49 }, (_, index) => {
          const theta = (index / 48) * Math.PI * 2;
          return [
            Math.sin(phi) * Math.cos(theta),
            Math.cos(phi),
            Math.sin(phi) * Math.sin(theta),
          ] as Point;
        }),
      );
    }
    for (let longitude = 0; longitude < 18; longitude++) {
      const theta = (longitude / 18) * Math.PI * 2;
      paths.push(
        Array.from({ length: 49 }, (_, index) => {
          const phi = (index / 48) * Math.PI * 2;
          return [
            Math.sin(phi) * Math.cos(theta),
            Math.cos(phi),
            Math.sin(phi) * Math.sin(theta),
          ] as Point;
        }),
      );
    }
    return paths;
  }, []);
  const path = (points: Point[], angle: number) =>
    points
      .map((point, index) => {
        const [x, y] = project(point, angle);
        return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  useEffect(() => {
    if (reduced) return;
    let frame = 0,
      previous = 0;
    const draw = (time: number) => {
      if (time - previous > 32) {
        geometry.forEach((points, index) =>
          lines.current[index]?.setAttribute("d", path(points, time * 0.00012)),
        );
        previous = time;
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [geometry, reduced]);
  return (
    <g fill="none" stroke="var(--sphere-wire)" strokeWidth="0.65" opacity="0.3">
      {geometry.map((points, index) => (
        <path
          key={index}
          ref={(element) => {
            if (element) lines.current[index] = element;
          }}
          d={path(points, 0)}
        />
      ))}
    </g>
  );
}

function Pulse({ event, index }: { event: Activity; index: number }) {
  const group = useRef<SVGGElement>(null);
  useEffect(() => {
    group.current
      ?.querySelectorAll<SVGAnimationElement>("animate, animateMotion")
      .forEach((animation) => {
        animation.beginElementAt(Number(animation.dataset.delay || 0));
      });
  }, []);
  const source = String(
    event.details.node_label || event.details.node_id || "Client",
  );
  const hash = Array.from(source).reduce(
    (value, char) => (value * 31 + char.charCodeAt(0)) >>> 0,
    7,
  );
  const angle = (hash % 628) / 100 + index * 0.7;
  const x = 320 + Math.cos(angle) * 290,
    y = 185 + Math.sin(angle) * 160;
  const targetX = 320 + Math.cos(angle) * 92,
    targetY = 185 + Math.sin(angle) * 92;
  const path = `M${x},${y} L${targetX},${targetY}`;
  const label = `${event.details.clipped ? "Clipped" : "Weights"} · ${source.slice(0, 24)}`;
  return (
    <g ref={group} data-event-sequence={event.sequence}>
      <title>{label}</title>
      <path d={path} stroke="var(--sphere-wire)" opacity="0.12" fill="none" />
      <g className="federation-projectile">
        <animateMotion
          begin="indefinite"
          dur="1.8s"
          path={path}
          fill="freeze"
          rotate="auto"
        />
        <animate
          begin="indefinite"
          attributeName="opacity"
          values="0;1;1;0"
          keyTimes="0;0.08;0.85;1"
          dur="1.8s"
          fill="freeze"
        />
        <path
          d="M-34,0 H-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          opacity="0.45"
        />
        <path d="M-6,-3 L5,0 L-6,3 Z" />
      </g>
      <g className="federation-projectile">
        <animateMotion
          begin="indefinite"
          dur="1.8s"
          path={path}
          fill="freeze"
        />
        <animate
          begin="indefinite"
          attributeName="opacity"
          values="0;1;1;0"
          keyTimes="0;0.08;0.75;1"
          dur="1.8s"
          fill="freeze"
        />
        <text
          x={Math.cos(angle) > 0 ? 12 : -12}
          y="-12"
          textAnchor={Math.cos(angle) > 0 ? "start" : "end"}
        >
          {label}
        </text>
      </g>
      <circle
        cx={targetX}
        cy={targetY}
        r="4"
        fill="none"
        stroke="var(--sphere-pulse)"
        opacity="0"
      >
        <animate
          begin="indefinite"
          attributeName="r"
          values="4;19"
          dur="0.45s"
          data-delay="1.45"
          fill="freeze"
        />
        <animate
          begin="indefinite"
          attributeName="opacity"
          values="0.7;0"
          dur="0.45s"
          data-delay="1.45"
          fill="freeze"
        />
      </circle>
    </g>
  );
}

export default function FederationGlobe({
  events,
  nodes,
  completed,
}: {
  events: Activity[];
  nodes: number;
  completed: number;
}) {
  const [pulses, setPulses] = useState<Activity[]>([]);
  const seen = useRef(events.at(-1)?.sequence ?? 0);
  const queue = useRef<Activity[]>([]);
  const [recent, setRecent] = useState("");
  const reduced = useMemo(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );
  useEffect(() => {
    const incoming = events.filter(
      (event) =>
        event.sequence > seen.current && event.kind === "contribution.accepted",
    );
    if (incoming.length) {
      const last = incoming.at(-1)!;
      setRecent(
        `Weights received · ${String(last.details.node_label || last.details.node_id || "Client")}`,
      );
      if (!reduced) queue.current = [...queue.current, ...incoming].slice(-120);
    }
    if (events.length) seen.current = events.at(-1)!.sequence;
  }, [events, reduced]);
  useEffect(() => {
    if (reduced) return;
    const timer = setInterval(() => {
      setPulses(queue.current.splice(0, 4));
    }, 1900);
    return () => clearInterval(timer);
  }, [reduced]);
  return (
    <div className="globe">
      <svg
        viewBox="0 0 640 370"
        role="img"
        aria-label="Federation sphere showing incoming accepted weight updates"
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          inset: 0,
        }}
      >
        <WireSphere reduced={reduced} />
        <circle
          cx="320"
          cy="185"
          r="68"
          fill="var(--sphere-core)"
          fillOpacity="0.65"
          stroke="var(--sphere-wire)"
          strokeOpacity="0.15"
        />
        {pulses.map((event, index) => (
          <Pulse key={event.sequence} event={event} index={index} />
        ))}
      </svg>
      <div className="globe-label">
        <span>FEDERATED COORDINATOR</span>
        <strong>
          {nodes}
          <small> clients</small>
        </strong>
        <span>{completed} completed experiments</span>
      </div>
      <div className="globe-caption">
        {recent || "Incoming weights appear here when a client contributes"}
      </div>
    </div>
  );
}
