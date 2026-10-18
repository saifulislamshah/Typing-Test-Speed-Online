// A light, short confetti burst. Skipped entirely under prefers-reduced-motion.
import { reducedMotion } from './util.js';

const COLORS = ['#2563eb', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4'];

export function burst(root) {
  if (reducedMotion()) return;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < 48; i++) {
    const p = document.createElement('i');
    p.style.left = `${Math.random() * 100}%`;
    p.style.background = COLORS[i % COLORS.length];
    p.style.setProperty('--dx', `${Math.random() * 160 - 80}px`);
    p.style.setProperty('--r', `${Math.random() * 720 - 360}deg`);
    p.style.animationDelay = `${0.25 + Math.random() * 0.3}s`;
    frag.append(p);
  }
  root.replaceChildren(frag);
  setTimeout(() => root.replaceChildren(), 2400);
}
