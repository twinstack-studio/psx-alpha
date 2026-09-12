"use client";

/**
 * Motion primitives.
 *
 * Everything here is scroll- or pointer-driven rather than time-driven, so the
 * page reacts to the reader instead of playing at them. Each primitive checks
 * `useReducedMotion` and degrades to a static render, which keeps the dashboard
 * usable for anyone who has asked their system for less movement.
 */

import {
  motion,
  useInView,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
} from "motion/react";
import {
  Children,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

const EASE = [0.22, 1, 0.36, 1] as const;

/* ==========================================================================
   ScrollProgress: a hairline across the top that tracks read position.
   ========================================================================== */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const width = useSpring(scrollYProgress, { stiffness: 140, damping: 26, restDelta: 0.001 });
  const reduce = useReducedMotion();
  if (reduce) return null;

  return (
    <motion.div
      aria-hidden
      className="fixed inset-x-0 top-0 z-[60] h-[2px] origin-left"
      style={{
        scaleX: width,
        background: "linear-gradient(90deg, var(--brand), var(--brand-2) 55%, var(--brand-3))",
        boxShadow: "0 0 12px rgba(109,141,255,.6)",
      }}
    />
  );
}

/* ==========================================================================
   Tilt: a card that leans towards the pointer, with a specular highlight
   tracking the same position.
   ========================================================================== */
export function Tilt({
  children,
  className = "",
  max = 7,
  glare = true,
  scale = 1.012,
}: {
  children: ReactNode;
  className?: string;
  /** Maximum lean in degrees on each axis. */
  max?: number;
  glare?: boolean;
  scale?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  // -0.5 … 0.5, the pointer's position within the card.
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const lift = useMotionValue(0);

  const spring = { stiffness: 260, damping: 24, mass: 0.4 };
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [max, -max]), spring);
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-max, max]), spring);
  const s = useSpring(lift, spring);
  const scaleV = useTransform(s, [0, 1], [1, scale]);

  // Percentage coordinates for the glare, written straight into a gradient.
  const gx = useTransform(px, (v) => `${(v + 0.5) * 100}%`);
  const gy = useTransform(py, (v) => `${(v + 0.5) * 100}%`);
  const glareOpacity = useTransform(s, [0, 1], [0, 1]);
  const glareBg = useMotionTemplate`radial-gradient(380px circle at ${gx} ${gy}, rgba(255,255,255,.09), transparent 62%)`;

  if (reduce) return <div className={className}>{children}</div>;

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width - 0.5);
    py.set((e.clientY - r.top) / r.height - 0.5);
  };

  return (
    <motion.div
      ref={ref}
      className={`relative ${className}`}
      style={{ rotateX, rotateY, scale: scaleV, transformStyle: "preserve-3d", perspective: 1100 }}
      onPointerMove={onMove}
      onPointerEnter={() => lift.set(1)}
      onPointerLeave={() => {
        lift.set(0);
        px.set(0);
        py.set(0);
      }}
    >
      {children}
      {glare && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit]"
          style={{ background: glareBg, opacity: glareOpacity }}
        />
      )}
    </motion.div>
  );
}

/* ==========================================================================
   Spotlight: a border that lights up under the cursor. Cheaper than Tilt —
   no transform, so it is safe to wrap dozens of rows in it.
   ========================================================================== */
export function Spotlight({
  children,
  className = "",
  color = "rgba(109,141,255,.30)",
  size = 320,
}: {
  children: ReactNode;
  className?: string;
  color?: string;
  size?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(-9999);
  const y = useMotionValue(-9999);
  const reduce = useReducedMotion();
  const bg = useMotionTemplate`radial-gradient(${size}px circle at ${x}px ${y}px, ${color}, transparent 70%)`;

  if (reduce) return <div className={className}>{children}</div>;

  return (
    <div
      ref={ref}
      className={`group relative ${className}`}
      onPointerMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        x.set(e.clientX - r.left);
        y.set(e.clientY - r.top);
      }}
      onPointerLeave={() => {
        x.set(-9999);
        y.set(-9999);
      }}
    >
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: bg }}
      />
      {children}
    </div>
  );
}

/* ==========================================================================
   Parallax: shifts a layer against the scroll it sits in.
   ========================================================================== */
export function Parallax({
  children,
  distance = 60,
  className = "",
}: {
  children: ReactNode;
  /** Pixels of travel across the element's full pass through the viewport. */
  distance?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [distance, -distance]);
  const smooth = useSpring(y, { stiffness: 110, damping: 26, mass: 0.4 });

  return (
    <div ref={ref} className={className}>
      <motion.div style={reduce ? undefined : { y: smooth }}>{children}</motion.div>
    </div>
  );
}

/* ==========================================================================
   FadeScale: scroll-linked opacity and scale, used to let a hero settle back
   as the reader moves past it.
   ========================================================================== */
export function ScrollFade({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const opacity = useTransform(scrollYProgress, [0, 0.85], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.965]);
  const y = useTransform(scrollYProgress, [0, 1], [0, 60]);

  return (
    <div ref={ref} className={className}>
      <motion.div style={reduce ? undefined : { opacity, scale, y }}>{children}</motion.div>
    </div>
  );
}

/* ==========================================================================
   Stagger: one <Stagger> around a list replaces a delay prop on every child.
   ========================================================================== */
export function Stagger({
  children,
  className = "",
  step = 0.055,
  y = 16,
  once = true,
}: {
  children: ReactNode;
  className?: string;
  step?: number;
  y?: number;
  once?: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once, margin: "-60px" }}
      variants={{ show: { transition: { staggerChildren: reduce ? 0 : step } } }}
    >
      {Children.map(children, (child, i) => (
        <motion.div
          key={i}
          variants={{
            hidden: { opacity: 0, y: reduce ? 0 : y },
            show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
          }}
        >
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}

/* ==========================================================================
   WordReveal: a headline that assembles word by word.
   ========================================================================== */
export function WordReveal({
  text,
  className = "",
  delay = 0,
  step = 0.045,
  style,
}: {
  text: string;
  className?: string;
  delay?: number;
  step?: number;
  style?: CSSProperties;
}) {
  const reduce = useReducedMotion();
  const words = text.split(" ");

  if (reduce) {
    return (
      <span className={className} style={style}>
        {text}
      </span>
    );
  }

  return (
    <motion.span
      className={className}
      style={style}
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: step, delayChildren: delay } } }}
      aria-label={text}
    >
      {words.map((w, i) => (
        // The clipping span gives each word a mask to rise out of.
        <span key={`${w}-${i}`} className="inline-block overflow-hidden align-bottom" aria-hidden>
          <motion.span
            className="inline-block"
            variants={{
              hidden: { y: "108%", opacity: 0 },
              show: { y: "0%", opacity: 1, transition: { duration: 0.72, ease: EASE } },
            }}
          >
            {w}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </motion.span>
  );
}

/* ==========================================================================
   Marquee: a seamless horizontal loop. The track is rendered twice and
   translated by exactly half its width, so the seam never shows.
   ========================================================================== */
export function Marquee({
  children,
  speed = 46,
  reverse = false,
  pauseOnHover = true,
  className = "",
}: {
  children: ReactNode;
  /** Pixels travelled per second. */
  speed?: number;
  reverse?: boolean;
  pauseOnHover?: boolean;
  className?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [duration, setDuration] = useState(28);
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.scrollWidth / 2;
      if (w > 0) setDuration(w / speed);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [speed]);

  return (
    <div className={`marquee ${pauseOnHover ? "marquee-pausable" : ""} ${className}`}>
      <div
        ref={trackRef}
        className="marquee-track"
        style={
          reduce
            ? undefined
            : ({
                animationDuration: `${duration}s`,
                animationDirection: reverse ? "reverse" : "normal",
              } as CSSProperties)
        }
      >
        {children}
        <span aria-hidden className="contents">
          {children}
        </span>
      </div>
    </div>
  );
}

/* ==========================================================================
   Magnetic: pulls towards the cursor while it is nearby.
   ========================================================================== */
export function Magnetic({
  children,
  strength = 0.28,
  className = "",
}: {
  children: ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useSpring(useMotionValue(0), { stiffness: 320, damping: 22, mass: 0.3 });
  const y = useSpring(useMotionValue(0), { stiffness: 320, damping: 22, mass: 0.3 });

  if (reduce) return <div className={className}>{children}</div>;

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ x, y }}
      onPointerMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        x.set((e.clientX - (r.left + r.width / 2)) * strength);
        y.set((e.clientY - (r.top + r.height / 2)) * strength);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}

/* ==========================================================================
   ScrollSkew: leans content by how fast the page is moving. Subtle enough to
   read as momentum rather than as an effect.
   ========================================================================== */
export function ScrollSkew({ children, className = "" }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const velocity = useVelocity(scrollY);
  const smooth = useSpring(velocity, { stiffness: 300, damping: 46 });
  const skewY = useTransform(smooth, [-2200, 0, 2200], [1.6, 0, -1.6], { clamp: true });

  return (
    <motion.div className={className} style={reduce ? undefined : { skewY }}>
      {children}
    </motion.div>
  );
}

/* ==========================================================================
   CountOnScroll: fires a callback the first time the wrapper is seen. Used by
   charts that draw themselves rather than animating a value.
   ========================================================================== */
export function WhenVisible({
  children,
  className = "",
  margin = "-80px",
}: {
  children: (visible: boolean) => ReactNode;
  className?: string;
  margin?: `${number}px`;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin });
  return (
    <div ref={ref} className={className}>
      {children(inView)}
    </div>
  );
}
